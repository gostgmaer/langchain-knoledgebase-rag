# Router documents
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile, status

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    DEFAULT_USER_ID,
    get_scoped_container,
    request_scoped_session,
    require_uuid_header,
)
from packages.api.responses import ApiResponse
from packages.api.schemas.document import (
    DocumentListResponseSchema,
    DocumentResponseSchema,
    DocumentUploadResponseSchema,
)
from packages.config.loader import settings
from packages.conversation.bootstrap import ensure_default_model_profile
from packages.domain.enums.document_status import DocumentStatus
from packages.infrastructure.container import ApplicationContainer
from packages.knowledge.bootstrap import ensure_default_knowledge_base
from packages.knowledge.schemas import ChunkingStrategy, IngestionRequest
from packages.sdk.common.exceptions import SDKException
from packages.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
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
    chunking_strategy: ChunkingStrategy = "auto",
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    user_id = require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID)

    knowledge_bases = container.repositories.knowledge_base()
    model_profiles = container.repositories.model_profile()

    knowledge_base = await ensure_default_knowledge_base(tenant_id, knowledge_bases)
    model_profile = await ensure_default_model_profile(model_profiles)

    content = await file.read()

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
    )

    background_tasks.add_task(
        _ingest_in_background,
        container,
        ingestion_request,
        scratch_path,
    )

    return ApiResponse(
        message="Document accepted for background ingestion.",
        data=DocumentUploadResponseSchema(
            status=DocumentStatus.PENDING,
            document_name=file.filename,
            file_id=uploaded_file.id,
        ),
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[DocumentListResponseSchema],
    summary="List documents",
    description="Lists a tenant's documents, most recently ingested first, across every knowledge base it owns.",
)
async def list_documents(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    documents = container.repositories.document()

    total = await documents.count_by_tenant(tenant_id)
    rows = await documents.list_by_tenant(tenant_id, limit=limit, offset=offset)

    return ApiResponse(
        message="Documents retrieved.",
        data=DocumentListResponseSchema(
            total=total,
            limit=limit,
            offset=offset,
            documents=[DocumentResponseSchema.model_validate(d) for d in rows],
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
        data=DocumentResponseSchema.model_validate(document),
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

    return ApiResponse(message="Document deleted.")


async def _ingest_in_background(
    container: ApplicationContainer,
    ingestion_request: IngestionRequest,
    scratch_path: Path,
) -> None:
    """
    Runs the real ingestion pipeline after the response has already
    been sent. Opens its own fresh request-scoped session rather than
    reusing the original request's — that session may already be
    closed by the time this runs, since background tasks execute
    after the response, not necessarily before request-scoped
    dependency cleanup.
    """

    try:
        async with request_scoped_session(container):
            pipeline = container.rag.ingestion_pipeline()
            response = await pipeline.ingest(ingestion_request)

            logger.info(
                "Background ingestion finished",
                document_id=str(response.document_id),
                skipped=response.skipped,
                chunk_count=response.chunk_count,
            )

    except Exception as exc:
        logger.exception(
            "Background ingestion failed",
            document_name=ingestion_request.document_name,
            error=str(exc),
        )

    finally:
        scratch_path.unlink(missing_ok=True)
