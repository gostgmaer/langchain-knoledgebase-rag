"""
AuditService (packages/application/services/audit_service.py) — only its standalone `clean_detail`
helper had any test coverage before this (tests/unit/test_provenance_security.py); `AuditService`
itself, the class every real audit write goes through, was zero-coverage despite backing the
"Audit & observability: strong" and "Secrets & data protection: strong" claims. Real Postgres via
the `session_factory` fixture (tests/conftest.py), matching the pattern used for
ConversationService/MessageService (docs/BUGS.md F3).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from packages.application.services.audit_service import AuditService
from packages.domain.models.audit_event import AuditEvent

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_record_persists_a_real_row_with_the_given_fields(db_session, session_factory):
    tenant_id = uuid4()
    actor_id = uuid4()
    resource_id = uuid4()
    service = AuditService(session_factory)

    await service.record(
        tenant_id=tenant_id,
        actor_id=actor_id,
        action="document.processed",
        resource_type="document",
        resource_id=resource_id,
        detail={"file_name": "policy.pdf", "chunk_count": 12},
    )

    row = (
        await db_session.execute(select(AuditEvent).where(AuditEvent.tenant_id == tenant_id))
    ).scalar_one()
    assert row.actor_id == actor_id
    assert row.action == "document.processed"
    assert row.resource_type == "document"
    assert row.resource_id == resource_id
    assert row.detail == {"file_name": "policy.pdf", "chunk_count": 12}


@pytest.mark.asyncio
async def test_record_strips_forbidden_keys_before_the_row_ever_reaches_postgres(db_session, session_factory):
    tenant_id = uuid4()
    service = AuditService(session_factory)

    await service.record(
        tenant_id=tenant_id,
        action="chat.turn",
        resource_type="conversation",
        detail={"query": "what is my salary", "token": "secret-value", "turn_count": 3},
    )

    row = (
        await db_session.execute(select(AuditEvent).where(AuditEvent.tenant_id == tenant_id))
    ).scalar_one()
    assert row.detail == {"turn_count": 3}
    assert "secret-value" not in str(row.detail)


@pytest.mark.asyncio
async def test_record_defaults_actor_and_resource_id_to_none(db_session, session_factory):
    tenant_id = uuid4()
    service = AuditService(session_factory)

    await service.record(tenant_id=tenant_id, action="tenant.created", resource_type="tenant")

    row = (
        await db_session.execute(select(AuditEvent).where(AuditEvent.tenant_id == tenant_id))
    ).scalar_one()
    assert row.actor_id is None
    assert row.resource_id is None
    assert row.detail == {}


@pytest.mark.asyncio
async def test_a_broken_session_factory_never_raises_out_of_record():
    class Broken:
        async def __aenter__(self):
            raise RuntimeError("db down")

        async def __aexit__(self, *exc):
            return False

    await AuditService(lambda: Broken()).record(
        tenant_id=uuid4(), action="document.processed", resource_type="document"
    )  # must not raise
