"""
audit_ingestion (packages/application/services/ingestion_audit.py) — zero test coverage before
this (docs/BUGS.md F3): every document upload's audit trail (processed / duplicate skipped /
version created / processing failed) goes through this one function, and it was never verified to
emit the right action, or to skip emitting one at all for the no-op case. Real AuditService against
real Postgres via the `session_factory` fixture (tests/conftest.py), so what's asserted is the
actual row written, not a call recorded against a mock.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from packages.application.services.audit_service import AuditService
from packages.application.services.ingestion_audit import audit_ingestion
from packages.domain.models.audit_event import AuditEvent
from packages.knowledge.schemas import IngestionRequest, IngestionResponse

pytestmark = pytest.mark.integration


def _request(tenant_id, uploaded_by) -> IngestionRequest:
    return IngestionRequest(
        tenant_id=tenant_id,
        model_profile_id=uuid4(),
        knowledge_base_id=uuid4(),
        file=Path("policy.pdf"),
        document_name="policy.pdf",
        uploaded_by=uploaded_by,
    )


async def _actions_for(db_session, tenant_id) -> list[str]:
    rows = (
        await db_session.execute(
            select(AuditEvent).where(AuditEvent.tenant_id == tenant_id).order_by(AuditEvent.created_at.asc())
        )
    ).scalars().all()
    return [row.action for row in rows]


@pytest.mark.asyncio
async def test_a_processed_document_is_audited_as_processed(db_session, session_factory):
    tenant_id, uploaded_by = uuid4(), uuid4()
    audit = AuditService(session_factory)
    document_id = uuid4()

    await audit_ingestion(
        audit,
        _request(tenant_id, uploaded_by),
        response=IngestionResponse(document_id=document_id, chunk_count=5, embedding_count=5),
    )

    assert await _actions_for(db_session, tenant_id) == ["document.processed"]
    row = (await db_session.execute(select(AuditEvent).where(AuditEvent.tenant_id == tenant_id))).scalar_one()
    assert row.resource_id == document_id
    assert row.actor_id == uploaded_by
    assert row.detail == {"file_name": "policy.pdf", "chunk_count": 5}


@pytest.mark.asyncio
async def test_a_new_version_also_gets_a_second_version_created_event(db_session, session_factory):
    tenant_id, uploaded_by = uuid4(), uuid4()
    audit = AuditService(session_factory)
    document_id, superseded_id = uuid4(), uuid4()

    await audit_ingestion(
        audit,
        _request(tenant_id, uploaded_by),
        response=IngestionResponse(
            document_id=document_id, chunk_count=5, embedding_count=5, superseded_document_id=superseded_id
        ),
    )

    assert await _actions_for(db_session, tenant_id) == ["document.processed", "document.version_created"]
    version_row = (
        await db_session.execute(
            select(AuditEvent).where(AuditEvent.tenant_id == tenant_id, AuditEvent.action == "document.version_created")
        )
    ).scalar_one()
    assert version_row.detail["supersedes"] == str(superseded_id)


@pytest.mark.asyncio
async def test_a_skipped_duplicate_is_audited_once_as_duplicate_skipped(db_session, session_factory):
    tenant_id, uploaded_by = uuid4(), uuid4()
    audit = AuditService(session_factory)
    document_id = uuid4()

    await audit_ingestion(
        audit,
        _request(tenant_id, uploaded_by),
        response=IngestionResponse(document_id=document_id, chunk_count=0, embedding_count=0, skipped=True),
    )

    assert await _actions_for(db_session, tenant_id) == ["document.duplicate_skipped"]


@pytest.mark.asyncio
async def test_a_failure_is_audited_as_processing_failed_with_its_stage(db_session, session_factory):
    tenant_id, uploaded_by = uuid4(), uuid4()
    audit = AuditService(session_factory)

    class _StageError(Exception):
        ingestion_stage = "embedding"

    await audit_ingestion(audit, _request(tenant_id, uploaded_by), error=_StageError("embed failed"))

    assert await _actions_for(db_session, tenant_id) == ["document.processing_failed"]
    row = (await db_session.execute(select(AuditEvent).where(AuditEvent.tenant_id == tenant_id))).scalar_one()
    assert row.detail == {"file_name": "policy.pdf", "stage": "embedding"}
    assert row.resource_id is None


@pytest.mark.asyncio
async def test_a_failure_with_no_stage_attribute_falls_back_to_unknown(db_session, session_factory):
    tenant_id, uploaded_by = uuid4(), uuid4()
    audit = AuditService(session_factory)

    await audit_ingestion(audit, _request(tenant_id, uploaded_by), error=RuntimeError("boom"))

    row = (await db_session.execute(select(AuditEvent).where(AuditEvent.tenant_id == tenant_id))).scalar_one()
    assert row.detail["stage"] == "unknown"


@pytest.mark.asyncio
async def test_no_response_and_no_error_writes_no_audit_event_at_all(db_session, session_factory):
    tenant_id, uploaded_by = uuid4(), uuid4()
    audit = AuditService(session_factory)

    await audit_ingestion(audit, _request(tenant_id, uploaded_by))

    assert await _actions_for(db_session, tenant_id) == []
