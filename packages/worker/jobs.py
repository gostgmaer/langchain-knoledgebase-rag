from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from uuid import UUID

from packages.api.dependencies import request_scoped_session
from packages.config.loader import settings
from packages.infrastructure.container import ApplicationContainer
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
