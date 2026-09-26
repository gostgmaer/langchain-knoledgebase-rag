# Router documents
from __future__ import annotations

import re
from typing import Literal
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel
from sqlalchemy import select
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile, status

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    DEFAULT_USER_ID,
    get_scoped_container,
    request_scoped_session,
    require_uuid_header,
    require_admin,
)
from packages.api.responses import ApiResponse
from packages.api.schemas.document import (
    ChunkingInfoSchema,
    DocumentChunkListResponseSchema,
    DocumentChunkResponseSchema,
    DocumentListResponseSchema,
    DocumentResponseSchema,
    DocumentUpdateSchema,
    DocumentUploadResponseSchema,
    DocumentVersionListResponseSchema,
    DocumentVersionResponseSchema,
)
from packages.application.services.ingestion_audit import audit_ingestion
from packages.application.services.reindex import run_reindex
from packages.config.loader import settings
from packages.conversation.bootstrap import ensure_default_model_profile
from packages.domain.enums.document_status import DocumentStatus
from packages.domain.models.knowledge_source import KnowledgeSource
from packages.domain.models.upload_job import UploadJob
from packages.infrastructure.container import ApplicationContainer
from packages.knowledge.pipelines.ingestion import PIPELINE_VERSION
from packages.knowledge.bootstrap import ensure_default_knowledge_base
from packages.knowledge.loaders.factory import LoaderFactory
from packages.knowledge.schemas import ChunkingStrategy, IngestionRequest
from packages.sdk.common.exceptions import SDKException
from packages.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
    dependencies=[Depends(require_admin())],
)


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[DocumentUploadResponseSchema],
    summary="Upload a document for ingestion",
    description=(
        "Stores the file in the Upload Service (the durable copy — see "
        "packages/sdk/upload), then schedules ingestion (load, clean, "
        "chunk, embed, store) as a background task against a local "
        "scratch copy, so the response doesn't wait for embedding work "
        "to finish. Re-uploading a file with unchanged content is "
        "detected via checksum and skipped rather than re-indexed."
    ),
)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    chunking_strategy: ChunkingStrategy = "recursive",
    document_type: str | None = Query(default=None, max_length=64),
    category: str | None = Query(default=None, max_length=64),
    tags: str | None = Query(default=None, description="Comma-separated tags."),
    visibility: Literal["tenant", "restricted"] = Query(
        default="tenant",
        description="'restricted' documents are retrievable by administrators only.",
    ),
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    user_id = require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID)

    knowledge_bases = container.repositories.knowledge_base()
    model_profiles = container.repositories.model_profile()

    knowledge_base = await ensure_default_knowledge_base(tenant_id, knowledge_bases)
    model_profile = await ensure_default_model_profile(model_profiles)

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must have a filename.",
        )

    extension = Path(file.filename).suffix.lower()
    if extension not in LoaderFactory.supported_extensions():
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type '{extension or '(none)'}'. "
                f"Supported: {', '.join(sorted(LoaderFactory.supported_extensions()))}."
            ),
        )

    content = await file.read()

    # Checked after reading, not against file.size — Starlette's
    # UploadFile.size isn't reliably populated for every upload
    # transport (multipart streaming can leave it None), but the
    # actual bytes read are always the real, correct length.
    if len(content) > settings.storage.max_file_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File is {len(content)} bytes, exceeding the "
                f"{settings.storage.max_file_size}-byte limit."
            ),
        )

    upload_client = container.upload.client()
    try:
        uploaded_file = await upload_client.uploads.upload(
            file=BytesIO(content),
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            tenant_id=str(tenant_id),
            user_id=str(user_id),
        )
    except httpx.HTTPError as exc:
        # The Upload Service itself never responded — a connectivity
        # problem (wrong UPLOAD_SERVICE_URL, service down), not
        # anything about this specific file.
        logger.error("Upload Service unreachable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Could not reach the Upload Service — check "
                "UPLOAD_SERVICE_URL is pointed at a running instance."
            ),
        ) from exc
    except SDKException as exc:
        # The Upload Service responded but rejected the request (e.g. a
        # disallowed file type — it maintains its own MIME allowlist,
        # confirmed live: plain text/octet-stream are both rejected,
        # application/pdf isn't). Surface its real message rather than
        # a generic one, since this is about the file, not connectivity.
        logger.warning("Upload Service rejected the file: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # A local scratch copy, deleted once ingestion finishes (packages/api/routers/documents.py
    # ::_ingest_in_background) — the Upload Service call above is the durable copy now, this is
    # only here because the loader/splitter pipeline (packages/knowledge/pipelines/ingestion.py)
    # needs a real local Path to read from.
    settings.storage.temp_directory.mkdir(parents=True, exist_ok=True)
    scratch_path = settings.storage.temp_directory / f"{uuid4()}_{file.filename}"
    scratch_path.write_bytes(content)

    ingestion_request = IngestionRequest(
        tenant_id=tenant_id,
        model_profile_id=model_profile.id,
        knowledge_base_id=knowledge_base.id,
        file=scratch_path,
        file_id=uploaded_file.id,
        document_name=file.filename,
        chunking_strategy=chunking_strategy,
        uploaded_by=user_id,
        document_type=document_type,
        category=category,
        tags=_parse_tags(tags),
        visibility=visibility,
    )

    upload_jobs = container.repositories.upload_job()
    upload_job = await upload_jobs.create(
        UploadJob(
            tenant_id=tenant_id,
            user_id=user_id,
            file_name=file.filename,
        )
    )

    await container.audit().record(
        tenant_id=tenant_id,
        actor_id=user_id,
        action="document.uploaded",
        resource_type="upload_job",
        resource_id=upload_job.id,
        detail={
            "file_name": file.filename,
            "size_bytes": len(content),
            "chunking_requested": chunking_strategy,
        },
    )

    pool = container.queue.pool()
    if pool is not None:
        # Real queued ingestion (packages/worker/jobs.py::ingest_document_job)
        # — gets retry on failure via the worker's max_tries, unlike the
        # in-process fallback below.
        job = await pool.enqueue_job(
            "ingest_document_job",
            ingestion_request,
            str(scratch_path),
            str(upload_job.id),
        )
        upload_job.job_id = job.job_id if job is not None else None
        await upload_jobs.update(upload_job)
    else:
        # Redis was unreachable at API startup (packages/api/lifespan.py) —
        # degrade to running ingestion in-process rather than failing the
        # upload outright.
        background_tasks.add_task(
            _ingest_in_background,
            container,
            ingestion_request,
            scratch_path,
            upload_job.id,
        )

    return ApiResponse(
        message="Document accepted for background ingestion.",
        data=DocumentUploadResponseSchema(
            status=DocumentStatus.PENDING,
            document_name=file.filename,
            file_id=uploaded_file.id,
            upload_job_id=upload_job.id,
        ),
    )


# A scratch file is saved as "<uuid4>_<original name>".
_SCRATCH_PREFIX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_")


def _parse_tags(raw: str | None) -> list[str] | None:
    """"a, b,,a" -> ["a", "b"] (trimmed, de-duplicated, order kept); None when empty."""
    if not raw:
        return None
    tags = list(dict.fromkeys(t.strip() for t in raw.split(",") if t.strip()))
    return tags or None


def _public_chunk_metadata(metadata: dict | None, document_name: str) -> dict:
    """
    Chunk metadata for display. Documents ingested before the loader stopped recording its scratch
    path have `source`/`filename` like "storage/temp/<uuid>_name.pdf": show the document's name
    instead of leaking the server's file layout.
    """
    cleaned = dict(metadata or {})
    for key in ("source", "filename"):
        value = cleaned.get(key)
        if isinstance(value, str) and (
            "storage/temp" in value
            or "\\" in value
            or value.startswith("/")
            or _SCRATCH_PREFIX.match(value)
        ):
            cleaned[key] = document_name
    return cleaned


def _chunking_info(metadata: dict | None) -> ChunkingInfoSchema | None:
    record = (metadata or {}).get("chunking")
    return ChunkingInfoSchema.model_validate(record) if isinstance(record, dict) else None


async def _document_responses(container: ApplicationContainer, rows) -> list[DocumentResponseSchema]:
    """Document rows -> API objects, with real chunk counts from one grouped query."""
    counts = await container.repositories.document_chunk().count_primary_by_documents(
        [d.id for d in rows],
    )

    source_ids = {d.source_id for d in rows if d.source_id}
    source_names: dict = {}
    if source_ids:
        found = await container.database.session().execute(select(KnowledgeSource.id, KnowledgeSource.name).where(KnowledgeSource.id.in_(source_ids)))
        source_names = {sid: name for sid, name in found.all()}

    responses = []
    for d in rows:
        primary, extra = counts.get(d.id, (0, 0))
        responses.append(
            DocumentResponseSchema(
                id=d.id,
                knowledge_base_id=d.knowledge_base_id,
                title=d.title,
                description=d.description,
                file_id=d.file_id,
                file_name=d.file_name,
                mime_type=d.mime_type,
                extension=d.extension,
                size_bytes=d.size_bytes,
                status=d.status.value if hasattr(d.status, "value") else str(d.status),
                is_current=d.is_current,
                created_at=d.created_at,
                updated_at=d.updated_at,
                chunk_count=primary,
                representation_count=extra,
                chunking=_chunking_info(d.metadata_),
                document_metadata=d.metadata_ or {},
                content_hash=d.checksum,
                uploaded_by=d.uploaded_by,
                processing_version=d.processing_version,
                parser_name=d.parser_name,
                chunking_version=d.chunking_version,
                embedding_provider=d.embedding_provider,
                embedding_model=d.embedding_model,
                embedding_dimensions=d.embedding_dimensions,
                processing_stage=d.processing_stage,
                error_reason=d.error_reason,
                processed_at=d.processed_at,
                visibility=d.visibility or "tenant",
                source_type=d.source_type or "upload",
                source_id=d.source_id,
                source_name=source_names.get(d.source_id),
                external_id=d.external_id,
                canonical_url=d.canonical_url,
                external_version=d.external_version,
                external_updated_at=d.external_updated_at,
                last_synced_at=d.last_synced_at,
                sync_id=d.sync_id,
                freshness_seconds=(
                    max(0, int((d.processed_at - d.external_updated_at).total_seconds()))
                    if d.external_updated_at and d.processed_at
                    else None
                ),
                allowed_roles=d.allowed_roles,
                allowed_users=d.allowed_users,
                document_type=d.document_type,
                category=d.category,
                tags=d.tags,
                embedding_is_stale=(
                    None if d.processing_version is None else d.processing_version != PIPELINE_VERSION
                ),
            )
        )
    return responses


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[DocumentListResponseSchema],
    summary="List documents",
    description=(
        "Lists a tenant's documents, most recently ingested first, across every knowledge base it owns "
        "(or one, with `knowledge_base_id`). Each document includes how it was chunked and its chunk count."
    ),
)
async def list_documents(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    knowledge_base_id: UUID | None = Query(default=None),
    source_id: UUID | None = Query(default=None, description="Only documents from this knowledge source."),
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    documents = container.repositories.document()

    total = await documents.count_by_tenant(tenant_id, knowledge_base_id, source_id)
    rows = await documents.list_by_tenant(
        tenant_id,
        limit=limit,
        offset=offset,
        knowledge_base_id=knowledge_base_id,
        source_id=source_id,
    )

    return ApiResponse(
        message="Documents retrieved.",
        data=DocumentListResponseSchema(
            total=total,
            limit=limit,
            offset=offset,
            documents=await _document_responses(container, rows),
        ),
    )


@router.get(
    "/{document_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[DocumentResponseSchema],
    summary="Fetch a document",
    description="Fetches a single document's metadata by ID.",
)
async def get_document(
    document_id: UUID,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    documents = container.repositories.document()
    document = await documents.get(document_id)

    if document is None or document.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    return ApiResponse(
        message="Document retrieved.",
        data=(await _document_responses(container, [document]))[0],
    )


@router.get(
    "/{document_id}/chunks",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[DocumentChunkListResponseSchema],
    summary="List a document's chunks",
    description=(
        "Every stored chunk of one document, in reading order, with its full text and all "
        "metadata (page, section, heading path, chunking strategy, offsets, token and character "
        "counts, ingestion time...). The document's summary/graph representations, which have a "
        "negative chunk_index, come first and are labelled by `kind`."
    ),
)
async def list_document_chunks(
    document_id: UUID,
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    documents = container.repositories.document()
    document = await documents.get(document_id)

    if document is None or document.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    if offset == 0:
        # Reading a document's full chunk text is an access event (one per viewing, not per page).
        await container.audit().record(
            tenant_id=tenant_id,
            actor_id=require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID),
            action="document.viewed",
            resource_type="document",
            resource_id=document_id,
            detail={"file_name": document.file_name},
        )

    chunks = container.repositories.document_chunk()
    total = await chunks.count_by_document(document_id)
    rows = await chunks.list_page_by_document(document_id, limit=limit, offset=offset)

    return ApiResponse(
        message="Chunks retrieved.",
        data=DocumentChunkListResponseSchema(
            document_id=document_id,
            total=total,
            limit=limit,
            offset=offset,
            chunking=_chunking_info(document.metadata_),
            chunks=[
                DocumentChunkResponseSchema(
                    id=c.id,
                    chunk_index=c.chunk_index,
                    kind=str((c.metadata_ or {}).get("representation_type") or "chunk"),
                    page_number=c.page_number,
                    section=c.section,
                    content=c.content,
                    token_count=c.token_count,
                    character_count=c.character_count,
                    start_offset=c.start_offset,
                    end_offset=c.end_offset,
                    metadata=_public_chunk_metadata(c.metadata_, document.file_name),
                    content_hash=c.content_hash,
                    chunking_strategy=c.chunking_strategy,
                    chunking_version=c.chunking_version,
                    embedding_provider=c.embedding_provider,
                    embedding_model=c.embedding_model,
                    embedding_dimensions=c.embedding_dimensions,
                    pipeline_version=c.pipeline_version,
                    indexed_at=c.indexed_at,
                )
                for c in rows
            ],
        ),
    )


@router.get(
    "/{document_id}/versions",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[DocumentVersionListResponseSchema],
    summary="List a document's version history",
    description=(
        "Lists every version in this document's re-upload lineage, oldest "
        "first. A document that has never been re-uploaded with changed "
        "content has an empty list here — versioning only starts once a "
        "second upload with the same filename but different content arrives."
    ),
)
async def list_document_versions(
    document_id: UUID,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    documents = container.repositories.document()
    document = await documents.get(document_id)

    if document is None or document.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    document_versions = container.repositories.document_version()
    own_version = await document_versions.get_by_document(document_id)

    if own_version is None:
        return ApiResponse(
            message="This document has no version history yet.",
            data=DocumentVersionListResponseSchema(
                root_document_id=document_id,
                versions=[],
            ),
        )

    rows = await document_versions.list_by_root(own_version.root_document_id)

    return ApiResponse(
        message="Document versions retrieved.",
        data=DocumentVersionListResponseSchema(
            root_document_id=own_version.root_document_id,
            versions=[
                DocumentVersionResponseSchema(
                    document_id=v.document_id,
                    version_number=v.version_number,
                    superseded_at=v.superseded_at,
                    is_current=v.superseded_at is None,
                )
                for v in rows
            ],
        ),
    )


class ReindexResponseSchema(BaseModel):
    queued: int
    skipped: int = 0


async def _queue_reindex(
    container: ApplicationContainer,
    background_tasks: BackgroundTasks,
    document_ids: list[UUID],
    actor_id: UUID,
) -> None:
    """Queue on the worker when Redis is up; otherwise run after the response, in-process."""
    pool = container.queue.pool()
    for document_id in document_ids:
        if pool is not None:
            await pool.enqueue_job("reindex_document_job", str(document_id), str(actor_id))
        else:
            background_tasks.add_task(run_reindex, container, document_id, actor_id)


@router.post(
    "/reindex-outdated",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[ReindexResponseSchema],
    summary="Re-index every document processed by an older (or unrecorded) pipeline",
    description=(
        "Queues a re-index for this workspace's current, ready documents whose recorded pipeline version "
        f"is not the running one (or was never recorded). Runs in the background, one document at a time "
        "per worker; the previous chunks stay searchable until each document's new ones are stored."
    ),
)
async def reindex_outdated(
    request: Request,
    background_tasks: BackgroundTasks,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    user_id = require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID)

    rows = await container.repositories.document().list_by_tenant(tenant_id, limit=200, offset=0)
    outdated = [
        d.id
        for d in rows
        if d.is_current and d.status == DocumentStatus.READY and d.processing_version != PIPELINE_VERSION
    ]
    await _queue_reindex(container, background_tasks, outdated, user_id)
    return ApiResponse(
        message="Re-index queued.",
        data=ReindexResponseSchema(queued=len(outdated), skipped=len(rows) - len(outdated)),
    )


@router.post(
    "/{document_id}/reindex",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[ReindexResponseSchema],
    summary="Re-index one document",
    description=(
        "Re-downloads the original file and re-runs chunking and embedding with the current pipeline and "
        "the strategy it was uploaded with. Use it to fill in provenance for older documents or pick up a "
        "changed embedding model."
    ),
)
async def reindex_document(
    document_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    user_id = require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID)

    document = await container.repositories.document().get(document_id)
    if document is None or document.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    if not document.is_current:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only the current version of a document can be re-indexed.",
        )

    await _queue_reindex(container, background_tasks, [document_id], user_id)
    return ApiResponse(message="Re-index queued.", data=ReindexResponseSchema(queued=1))


@router.patch(
    "/{document_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[DocumentResponseSchema],
    summary="Change a document's access level or classification",
    description=(
        "Sets `visibility` ('tenant' = every member may retrieve it, 'restricted' = administrators "
        "only), `document_type`, `category` and `tags`. Takes effect on the next retrieval: access is "
        "enforced inside the search query, nothing is re-indexed. Every change is audited."
    ),
)
async def update_document(
    document_id: UUID,
    payload: DocumentUpdateSchema,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    user_id = require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID)

    documents = container.repositories.document()
    document = await documents.get(document_id)

    if document is None or document.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    changes = payload.model_dump(exclude_unset=True)
    if "tags" in changes and changes["tags"] is not None:
        changes["tags"] = _parse_tags(",".join(changes["tags"]))
    for grant in ("allowed_roles", "allowed_users"):
        if changes.get(grant) is not None:
            changes[grant] = _parse_tags(",".join(changes[grant]))

    before = {field: getattr(document, field) for field in changes}
    for field, value in changes.items():
        setattr(document, field, value)
    await documents.update(document)

    audit = container.audit()
    if "visibility" in changes and (before["visibility"] or "tenant") != (changes["visibility"] or "tenant"):
        await audit.record(
            tenant_id=tenant_id,
            actor_id=user_id,
            action="document.access_changed",
            resource_type="document",
            resource_id=document_id,
            detail={"from": before["visibility"] or "tenant", "to": changes["visibility"] or "tenant"},
        )
    grant_fields = sorted({"allowed_roles", "allowed_users"} & set(changes))
    if grant_fields:
        await audit.record(
            tenant_id=tenant_id,
            actor_id=user_id,
            action="document.access_changed",
            resource_type="document",
            resource_id=document_id,
            detail={"grants_changed": grant_fields},
        )
    if set(changes) - {"visibility", "allowed_roles", "allowed_users"}:
        await audit.record(
            tenant_id=tenant_id,
            actor_id=user_id,
            action="document.metadata_updated",
            resource_type="document",
            resource_id=document_id,
            detail={"fields": sorted(set(changes) - {"visibility", "allowed_roles", "allowed_users"})},
        )

    return ApiResponse(
        message="Document updated.",
        data=(await _document_responses(container, [document]))[0],
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[None],
    summary="Delete a document",
    description=(
        "Deletes a document's chunks from the vector store and its "
        "bookkeeping row from Postgres. Does not delete the underlying "
        "file from the Upload Service — this only removes it from the "
        "knowledge base's search index."
    ),
)
async def delete_document(
    document_id: UUID,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    documents = container.repositories.document()
    document = await documents.get(document_id)

    if document is None or document.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    knowledge_manager = container.rag.knowledge_manager()
    await knowledge_manager.delete_document(tenant_id=tenant_id, document_id=document_id)
    await documents.delete(document)

    await container.audit().record(
        tenant_id=tenant_id,
        actor_id=require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID),
        action="document.deleted",
        resource_type="document",
        resource_id=document_id,
        detail={"file_name": document.file_name},
    )

    return ApiResponse(message="Document deleted.")


async def _ingest_in_background(
    container: ApplicationContainer,
    ingestion_request: IngestionRequest,
    scratch_path: Path,
    upload_job_id: UUID,
) -> None:
    """
    Fallback ingestion path, used only when the arq job queue was
    unreachable at API startup (see the `pool is None` branch in
    `upload_document` above and packages/api/lifespan.py) — otherwise
    packages/worker/jobs.py::ingest_document_job handles this instead,
    with real retry on failure. Opens its own fresh request-scoped
    session rather than reusing the original request's — that session
    may already be closed by the time this runs, since background
    tasks execute after the response, not necessarily before
    request-scoped dependency cleanup.
    """

    try:
        async with request_scoped_session(container):
            upload_jobs = container.repositories.upload_job()
            upload_job = await upload_jobs.get(upload_job_id)
            if upload_job is not None:
                await upload_jobs.mark_running(upload_job)

            pipeline = container.rag.ingestion_pipeline()
            response = await pipeline.ingest(ingestion_request)

            logger.info(
                "Background ingestion finished",
                document_id=str(response.document_id),
                skipped=response.skipped,
                chunk_count=response.chunk_count,
            )

            if upload_job is not None:
                await upload_jobs.mark_succeeded(upload_job, response.document_id)

            await audit_ingestion(container.audit(), ingestion_request, response)

    except Exception as exc:
        logger.exception(
            "Background ingestion failed",
            document_name=ingestion_request.document_name,
            error=str(exc),
        )
        await audit_ingestion(container.audit(), ingestion_request, error=exc)

        try:
            async with request_scoped_session(container):
                upload_jobs = container.repositories.upload_job()
                upload_job = await upload_jobs.get(upload_job_id)
                if upload_job is not None:
                    await upload_jobs.mark_failed(
                    upload_job,
                    f"[{getattr(exc, 'ingestion_stage', 'unknown')}] {exc}",
                )
        except Exception:
            logger.exception("Could not record upload job failure")

    finally:
        scratch_path.unlink(missing_ok=True)
