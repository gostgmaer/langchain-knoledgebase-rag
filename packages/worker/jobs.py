from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from packages.api.dependencies import request_scoped_session
from packages.config.loader import settings
from packages.domain.enums.conversation_status import ConversationStatus
from packages.infrastructure.container import ApplicationContainer
from packages.infrastructure.container.graph import create_postgres_checkpointer
from packages.knowledge.schemas import IngestionRequest
from packages.shared.logging import get_logger

logger = get_logger(__name__)

# Scratch files are supposed to be deleted right after ingestion
# finishes (this module's own `ingest_document_job`, or
# packages/api/routers/documents.py's `_ingest_in_background` fallback
# when the queue is unreachable) — this is a defense-in-depth sweep for
# anything that survives a crash or a killed process mid-ingestion, not
# the primary cleanup mechanism. An hour is generous: real ingestion
# runs finish in seconds.
_MAX_AGE_SECONDS = 3600


async def cleanup_orphaned_scratch_files(ctx: dict[str, Any]) -> dict[str, int]:
    """
    Deletes any file under `settings.storage.temp_directory` older than
    `_MAX_AGE_SECONDS`. `ctx` is arq's per-job context (Redis pool, job
    id, etc.) — unused here since this job is self-contained, but arq
    always calls job functions with it as the first argument.
    """

    temp_dir = settings.storage.temp_directory

    if not temp_dir.exists():
        return {"checked": 0, "deleted": 0}

    now = time.time()
    checked = 0
    deleted = 0

    for path in temp_dir.iterdir():
        if not path.is_file():
            continue

        checked += 1

        if now - path.stat().st_mtime > _MAX_AGE_SECONDS:
            path.unlink(missing_ok=True)
            deleted += 1
            logger.info("Deleted orphaned scratch file", path=str(path))

    logger.info(
        "Scratch cleanup finished",
        checked=checked,
        deleted=deleted,
    )

    return {"checked": checked, "deleted": deleted}


async def ingest_document_job(
    ctx: dict[str, Any],
    ingestion_request: IngestionRequest,
    scratch_path: str,
    upload_job_id: str,
) -> dict[str, Any]:
    """
    Real document ingestion (load, clean, chunk, embed, store), run as
    an arq job instead of a FastAPI `BackgroundTasks` callback — the
    queued counterpart to packages/api/routers/documents.py's
    `_ingest_in_background`, which now only runs when Redis was
    unreachable at API startup. `ctx["container"]` is the worker's own
    long-lived `ApplicationContainer`, set up once in
    packages/worker/main.py's `_on_startup` — `request_scoped_session`
    gives this job its own fresh DB session/transaction, same as every
    other background task in this app. `upload_job_id` identifies the
    real UploadJob row (packages/domain/models/upload_job.py) to update
    as this job progresses — looked up by our own primary key, not
    arq's job id, so the fallback in-process path can update the exact
    same kind of row without ever touching arq.
    """

    container: ApplicationContainer = ctx["container"]
    path = Path(scratch_path)
    job_uuid = UUID(upload_job_id)

    try:
        async with request_scoped_session(container):
            upload_jobs = container.repositories.upload_job()
            upload_job = await upload_jobs.get(job_uuid)
            if upload_job is not None:
                await upload_jobs.mark_running(upload_job)

            pipeline = container.rag.ingestion_pipeline()
            response = await pipeline.ingest(ingestion_request)

            logger.info(
                "Queued ingestion finished",
                document_id=str(response.document_id),
                skipped=response.skipped,
                chunk_count=response.chunk_count,
            )

            if upload_job is not None:
                await upload_jobs.mark_succeeded(upload_job, response.document_id)

            return {
                "document_id": str(response.document_id),
                "skipped": response.skipped,
                "chunk_count": response.chunk_count,
            }

    except Exception as exc:
        logger.exception(
            "Queued ingestion failed",
            document_name=ingestion_request.document_name,
            error=str(exc),
        )

        try:
            async with request_scoped_session(container):
                upload_jobs = container.repositories.upload_job()
                upload_job = await upload_jobs.get(job_uuid)
                if upload_job is not None:
                    await upload_jobs.mark_failed(upload_job, str(exc))
        except Exception:
            logger.exception("Could not record upload job failure")

        raise

    finally:
        path.unlink(missing_ok=True)


async def reindex_stale_documents_job(ctx: dict[str, Any]) -> dict[str, int]:
    """
    Weekly sweep re-embedding documents not touched in
    settings.rag.reindex_stale_after_days — Scheduled Re-indexing
    (docs/mvpRAG.md v1.1), picking up embedding model changes or
    quality improvements without waiting for a manual re-upload. Each
    document is caught and logged independently so one bad document
    (e.g. the Upload Service genuinely doesn't have its file anymore)
    doesn't abort the whole sweep.
    """

    container: ApplicationContainer = ctx["container"]
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.rag.reindex_stale_after_days)

    reindexed = 0
    failed = 0

    async with request_scoped_session(container):
        documents = container.repositories.document()
        pipeline = container.rag.ingestion_pipeline()

        stale = await documents.list_stale(cutoff)

        for document in stale:
            try:
                await pipeline.reindex_document(document.id)
                reindexed += 1
                logger.info("Reindexed stale document", document_id=str(document.id))
            except Exception as exc:
                failed += 1
                logger.exception(
                    "Failed to reindex document",
                    document_id=str(document.id),
                    error=str(exc),
                )

    logger.info("Scheduled reindex sweep finished", reindexed=reindexed, failed=failed)

    return {"reindexed": reindexed, "failed": failed}


async def cleanup_orphaned_chunks_job(ctx: dict[str, Any]) -> dict[str, int]:
    """
    Sweeps Chroma (the live vector-store backend — see
    packages/infrastructure/container/rag.py) for chunks whose
    document_id has no matching real Postgres `documents` row.
    `IngestionPipeline.ingest()` writes to Chroma before the enclosing
    Postgres transaction commits, so a crash between those two steps
    leaves real orphans; Postgres-side `DocumentChunk` orphans are
    already prevented by `ondelete="CASCADE"`, so only Chroma needs
    sweeping.

    Discovers candidate (tenant_id, document_id) pairs via
    `ChromaVectorStore.list_all_document_refs()` — a full collection
    scan, not derived from Postgres's own `documents` table. Confirmed
    live that deriving candidates from Postgres is wrong: a tenant
    whose *only* document's Postgres row is itself the orphan won't
    appear in that table at all, so it would silently never be swept.
    Falls back to a no-op (rather than raising) if the configured
    backend doesn't support this — only Chroma does; pgvector doesn't
    need it.
    """

    container: ApplicationContainer = ctx["container"]

    checked = 0
    orphaned_documents = 0

    async with request_scoped_session(container):
        documents = container.repositories.document()
        vectorstore = container.rag.vectorstore()
        store = vectorstore.store

        if not hasattr(store, "list_all_document_refs"):
            logger.info(
                "Vector store backend has no full-scan method — skipping orphan sweep",
                backend=type(store).__name__,
            )
            return {"checked": 0, "orphaned_documents": 0}

        refs = await store.list_all_document_refs(limit=100_000)
        checked = len(refs)

        document_ids = {document_id for _, document_id in refs}
        existing = await documents.exists_batch(list(document_ids)) if document_ids else set()

        for tenant_id, document_id in refs:
            if document_id in existing:
                continue

            await store.delete_document(tenant_id=tenant_id, document_id=document_id)
            orphaned_documents += 1
            logger.info(
                "Deleted orphaned chunks",
                tenant_id=str(tenant_id),
                document_id=str(document_id),
            )

    logger.info(
        "Orphaned chunk cleanup finished",
        checked=checked,
        orphaned_documents=orphaned_documents,
    )

    return {"checked": checked, "orphaned_documents": orphaned_documents}


async def expire_stale_conversations_job(ctx: dict[str, Any]) -> dict[str, int]:
    """
    Archives ACTIVE conversations with no activity for
    `settings.app.session_expiry_days`, and frees their LangGraph
    checkpoint data. The worker's own `ApplicationContainer` does not
    have the real Postgres checkpointer wired the way
    packages/api/lifespan.py wires it for the API process — this opens
    its own dedicated connection, mirroring lifespan.py's exact
    open/use/close pattern rather than going through
    `ctx["container"].graph.checkpointer()` (which would resolve to
    the in-memory default here, a no-op against an empty store).
    """

    container: ApplicationContainer = ctx["container"]
    # Conversation.last_message_at is TIMESTAMP WITHOUT TIME ZONE (this
    # app's established naive-UTC convention — see
    # ConversationService.touch()) — a timezone-aware cutoff here
    # raises asyncpg.exceptions.DataError, confirmed live.
    cutoff = datetime.utcnow() - timedelta(days=settings.app.session_expiry_days)

    expired = 0
    checkpointer = None

    try:
        checkpointer = await create_postgres_checkpointer()

        async with request_scoped_session(container):
            conversations = container.repositories.conversation()
            stale = await conversations.list_stale_active(cutoff)

            for conversation in stale:
                # .status directly, NOT conversations.archive() — that
                # method sets a column-less is_archived attribute that
                # never actually persists (see mark_status()'s own
                # docstring in packages/infrastructure/repositories/
                # conversation.py).
                await conversations.mark_status(conversation, ConversationStatus.ARCHIVED)
                await checkpointer.adelete_thread(str(conversation.id))
                expired += 1

    finally:
        if checkpointer is not None:
            await asyncio.to_thread(checkpointer.conn.close)

    logger.info("Expired stale conversations", expired=expired)

    return {"expired": expired}


async def cleanup_stale_upload_jobs_job(ctx: dict[str, Any]) -> dict[str, int]:
    """
    Marks `UploadJob` rows stuck in QUEUED/RUNNING for over an hour as
    FAILED — matches the existing scratch-file cleanup's own 1hr
    threshold precedent (real ingestion finishes in seconds; an hour
    is a generous "something genuinely got stuck" signal).
    """

    container: ApplicationContainer = ctx["container"]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)

    failed = 0

    async with request_scoped_session(container):
        upload_jobs = container.repositories.upload_job()
        stale = await upload_jobs.list_stale(cutoff)

        for job in stale:
            await upload_jobs.mark_failed(job, "Stale — exceeded max processing time")
            failed += 1

    logger.info("Marked stale upload jobs failed", failed=failed)

    return {"failed": failed}
