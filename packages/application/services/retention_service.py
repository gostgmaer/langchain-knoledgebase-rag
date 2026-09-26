# Retention service
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.config.loader import settings
from packages.domain.models.audit_event import AuditEvent
from packages.domain.models.retrieval_log import RetrievalLog, RetrievalResultLog


async def purge_expired(
    session_factory: Callable[[], AsyncSession] | async_sessionmaker,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """
    Deletes retrieval logs (and their per-chunk rows) and audit events older than the
    configured retention windows. A window of 0 keeps that table forever.
    Documents, versions and chunks are not touched here: they are removed by their own
    delete/supersede flows, never by age.
    """
    now = now or datetime.now(UTC)
    result = {"retrieval_logs": 0, "retrieval_results": 0, "audit_events": 0}

    async with session_factory() as session:
        days = settings.rag.retention_retrieval_log_days
        if days > 0:
            cutoff = now - timedelta(days=days)
            old_ids = RetrievalLog.__table__.select().with_only_columns(RetrievalLog.id).where(
                RetrievalLog.created_at < cutoff
            )
            results = await session.execute(
                delete(RetrievalResultLog).where(RetrievalResultLog.retrieval_id.in_(old_ids))
            )
            logs = await session.execute(delete(RetrievalLog).where(RetrievalLog.created_at < cutoff))
            result["retrieval_results"] = results.rowcount or 0
            result["retrieval_logs"] = logs.rowcount or 0

        days = settings.rag.retention_audit_days
        if days > 0:
            audit = await session.execute(
                delete(AuditEvent).where(AuditEvent.created_at < now - timedelta(days=days))
            )
            result["audit_events"] = audit.rowcount or 0

        await session.commit()

    return result
