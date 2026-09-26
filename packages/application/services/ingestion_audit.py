# Ingestion audit helper
from __future__ import annotations

from packages.application.services.audit_service import AuditService
from packages.knowledge.schemas import IngestionRequest, IngestionResponse


async def audit_ingestion(
    audit: AuditService,
    request: IngestionRequest,
    response: IngestionResponse | None = None,
    error: BaseException | None = None,
) -> None:
    """
    Audit events for the outcome of one ingestion: processed, duplicate skipped, new version
    created, or failed (with the pipeline stage that failed). Best-effort like every audit write.
    """
    base = {"file_name": request.document_name}

    if error is not None:
        await audit.record(
            tenant_id=request.tenant_id,
            actor_id=request.uploaded_by,
            action="document.processing_failed",
            resource_type="document",
            detail={**base, "stage": getattr(error, "ingestion_stage", "unknown")},
        )
        return

    if response is None:
        return

    if response.skipped:
        await audit.record(
            tenant_id=request.tenant_id,
            actor_id=request.uploaded_by,
            action="document.duplicate_skipped",
            resource_type="document",
            resource_id=response.document_id,
            detail=base,
        )
        return

    await audit.record(
        tenant_id=request.tenant_id,
        actor_id=request.uploaded_by,
        action="document.processed",
        resource_type="document",
        resource_id=response.document_id,
        detail={**base, "chunk_count": response.chunk_count},
    )
    if response.superseded_document_id is not None:
        await audit.record(
            tenant_id=request.tenant_id,
            actor_id=request.uploaded_by,
            action="document.version_created",
            resource_type="document",
            resource_id=response.document_id,
            detail={**base, "supersedes": str(response.superseded_document_id)},
        )
