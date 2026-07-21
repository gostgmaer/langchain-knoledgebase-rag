# Router documents
from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Request, UploadFile, status

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    DEFAULT_USER_ID,
    get_scoped_container,
    request_scoped_session,
    require_uuid_header,
)
from packages.api.responses import ApiResponse
from packages.api.schemas.document import DocumentUploadResponseSchema
from packages.config.loader import settings
from packages.conversation.bootstrap import ensure_default_model_profile
from packages.domain.enums.document_status import DocumentStatus
from packages.infrastructure.container import ApplicationContainer
from packages.knowledge.bootstrap import ensure_default_knowledge_base
from packages.knowledge.schemas import ChunkingStrategy, IngestionRequest
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
        "Accepts a file upload and schedules ingestion (load, clean, "
        "chunk, embed, store) as a background task, so the response "
        "doesn't wait for embedding work to finish. Re-uploading a "
        "file with unchanged content is detected via checksum and "
        "skipped rather than re-indexed."
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

    settings.storage.upload_directory.mkdir(parents=True, exist_ok=True)

    destination = settings.storage.upload_directory / f"{uuid4()}_{file.filename}"
    destination.write_bytes(await file.read())

    ingestion_request = IngestionRequest(
        tenant_id=tenant_id,
        model_profile_id=model_profile.id,
        knowledge_base_id=knowledge_base.id,
        file=destination,
        document_name=file.filename,
        chunking_strategy=chunking_strategy,
    )

    background_tasks.add_task(
        _ingest_in_background,
        container,
        ingestion_request,
    )

    return ApiResponse(
        message="Document accepted for background ingestion.",
        data=DocumentUploadResponseSchema(
            status=DocumentStatus.PENDING,
            document_name=file.filename,
        ),
    )


async def _ingest_in_background(
    container: ApplicationContainer,
    ingestion_request: IngestionRequest,
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
