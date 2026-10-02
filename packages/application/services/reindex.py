# Document reindex runner
from __future__ import annotations

from uuid import UUID

from packages.api.dependencies import request_scoped_session
from packages.infrastructure.container import ApplicationContainer
from packages.shared.logging import get_logger

logger = get_logger(__name__)


async def run_reindex(container: ApplicationContainer, document_id: UUID, actor_id: UUID | None) -> bool:
    """
    Re-runs load -> clean -> split -> embed -> store for one document (same document id) in its own
    session, then records the outcome in the audit trail. Returns True on success. A failure leaves
    the previous chunks in place (the pipeline works in one transaction) and is audited, not raised,
    so one bad document cannot stop a bulk reindex.
    """
    tenant_id: UUID | None = None
    file_name: str | None = None
    try:
        async with request_scoped_session(container):
            document = await container.repositories.document().get(document_id)
            if document is None:
                return False
            tenant_id, file_name = document.tenant_id, document.file_name
            await container.rag.ingestion_pipeline().reindex_document(document_id)

        await container.audit().record(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="document.reindexed",
            resource_type="document",
            resource_id=document_id,
            detail={"file_name": file_name, "trigger": "manual"},
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.exception("Reindex failed", document_id=str(document_id), error=str(exc))
        if tenant_id is not None:
            await container.audit().record(
                tenant_id=tenant_id,
                actor_id=actor_id,
                action="document.reindex_failed",
                resource_type="document",
                resource_id=document_id,
                detail={"file_name": file_name, "stage": getattr(exc, "ingestion_stage", "unknown")},
            )
        return False
