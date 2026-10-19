"""
retention_service.purge_expired (packages/application/services/retention_service.py) — zero test
coverage before this (docs/BUGS.md F3) despite being the only thing that ever deletes retrieval
logs or audit events, on a schedule an admin controls (docs/BUGS.md item 38). A bug here either
destroys data an admin expected kept (a cutoff computed wrong) or never purges data a compliance
retention window required gone (a window of 0 badly short-circuited into "purge everything"), so
this is exactly the kind of real deletion logic that should not ship untested. Real Postgres via
the `session_factory` fixture (tests/conftest.py).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from packages.application.services.retention_service import purge_expired
from packages.domain.models.audit_event import AuditEvent
from packages.domain.models.retrieval_log import RetrievalLog, RetrievalResultLog

pytestmark = pytest.mark.integration


def _retrieval_log(*, created_at: datetime, tenant_id=None) -> RetrievalLog:
    return RetrievalLog(
        tenant_id=tenant_id or uuid4(),
        query_hash="hash",
        strategy="hybrid",
        top_k=5,
        created_at=created_at,
    )


def _retrieval_result(retrieval_id, tenant_id) -> RetrievalResultLog:
    return RetrievalResultLog(
        retrieval_id=retrieval_id,
        tenant_id=tenant_id,
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        retrieval_rank=1,
        retrieval_score=1.0,
    )


def _audit_event(*, created_at: datetime) -> AuditEvent:
    return AuditEvent(
        tenant_id=uuid4(),
        action="document.processed",
        resource_type="document",
        created_at=created_at,
    )


@pytest.mark.asyncio
async def test_purges_retrieval_logs_older_than_the_cutoff_and_keeps_newer_ones(db_session, session_factory):
    now = datetime.now(UTC)
    old = _retrieval_log(created_at=now - timedelta(days=200))
    fresh = _retrieval_log(created_at=now - timedelta(days=1))
    db_session.add_all([old, fresh])
    await db_session.flush()
    db_session.add_all([_retrieval_result(old.id, old.tenant_id), _retrieval_result(fresh.id, fresh.tenant_id)])
    await db_session.commit()

    result = await purge_expired(session_factory, now=now, retrieval_log_days=90, audit_days=0)

    assert result["retrieval_logs"] >= 1
    assert result["retrieval_results"] >= 1
    remaining_ids = set((await db_session.execute(select(RetrievalLog.id))).scalars().all())
    assert old.id not in remaining_ids
    assert fresh.id in remaining_ids
    remaining_result_ids = set((await db_session.execute(select(RetrievalResultLog.retrieval_id))).scalars().all())
    assert old.id not in remaining_result_ids
    assert fresh.id in remaining_result_ids


@pytest.mark.asyncio
async def test_a_window_of_zero_keeps_retrieval_logs_forever(db_session, session_factory):
    now = datetime.now(UTC)
    ancient = _retrieval_log(created_at=now - timedelta(days=5000))
    db_session.add(ancient)
    await db_session.commit()

    result = await purge_expired(session_factory, now=now, retrieval_log_days=0, audit_days=0)

    assert result["retrieval_logs"] == 0
    remaining_ids = set((await db_session.execute(select(RetrievalLog.id))).scalars().all())
    assert ancient.id in remaining_ids


@pytest.mark.asyncio
async def test_purges_audit_events_older_than_the_cutoff_and_keeps_newer_ones(db_session, session_factory):
    now = datetime.now(UTC)
    old = _audit_event(created_at=now - timedelta(days=400))
    fresh = _audit_event(created_at=now - timedelta(days=1))
    db_session.add_all([old, fresh])
    await db_session.commit()

    result = await purge_expired(session_factory, now=now, retrieval_log_days=0, audit_days=365)

    assert result["audit_events"] >= 1
    remaining_ids = set((await db_session.execute(select(AuditEvent.id))).scalars().all())
    assert old.id not in remaining_ids
    assert fresh.id in remaining_ids


@pytest.mark.asyncio
async def test_a_window_of_zero_keeps_audit_events_forever(db_session, session_factory):
    now = datetime.now(UTC)
    ancient = _audit_event(created_at=now - timedelta(days=5000))
    db_session.add(ancient)
    await db_session.commit()

    result = await purge_expired(session_factory, now=now, retrieval_log_days=0, audit_days=0)

    assert result["audit_events"] == 0
    remaining_ids = set((await db_session.execute(select(AuditEvent.id))).scalars().all())
    assert ancient.id in remaining_ids


@pytest.mark.asyncio
async def test_explicit_none_windows_fall_back_to_the_platform_settings_built_in_defaults(db_session, session_factory):
    now = datetime.now(UTC)
    # Built-in defaults: retention_retrieval_log_days=90, retention_audit_days=365.
    old_log = _retrieval_log(created_at=now - timedelta(days=200))
    fresh_log = _retrieval_log(created_at=now - timedelta(days=10))
    db_session.add_all([old_log, fresh_log])
    await db_session.commit()

    result = await purge_expired(session_factory, now=now)

    assert result["retrieval_logs"] >= 1
    remaining_ids = set((await db_session.execute(select(RetrievalLog.id))).scalars().all())
    assert old_log.id not in remaining_ids
    assert fresh_log.id in remaining_ids
