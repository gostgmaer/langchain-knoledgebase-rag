"""
Creating, dispatching and scheduling sync runs.

A run is a row first (`queued`) and a queue message second: the row is the source of truth (status, cancel flag,
counters), so a lost message leaves a visible queued run that the reaper fails, never a silent gap. Only one
run per source may be queued or running.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select

from packages.api.dependencies import request_scoped_session
from packages.connectors.sync import STALE_RUN_MINUTES
from packages.domain.models.knowledge_source import KnowledgeSource, SourceSyncRun
from packages.infrastructure.container import ApplicationContainer
from packages.shared.logging import get_logger

logger = get_logger(__name__)

ACTIVE_RUN_STATUSES = ("queued", "running")


class SyncAlreadyRunning(RuntimeError):
    """The source already has a queued or running sync."""


class SourceNotSyncable(RuntimeError):
    """The source is paused or deleted."""


def _stale_cutoff() -> datetime:
    return datetime.now(UTC) - timedelta(minutes=STALE_RUN_MINUTES)


async def create_run(container: ApplicationContainer, source_id: UUID, tenant_id: UUID, *, trigger: str, actor_id: UUID | None) -> UUID:
    """Creates a queued run, or raises SyncAlreadyRunning / SourceNotSyncable / LookupError."""
    async with request_scoped_session(container) as session:
        source = await session.get(KnowledgeSource, source_id)
        if source is None or source.tenant_id != tenant_id or source.is_deleted:
            raise LookupError("Knowledge source not found.")
        if source.status == "paused" and trigger != "manual":
            raise SourceNotSyncable("The source is paused.")

        active = (
            await session.execute(
                select(SourceSyncRun).where(
                    SourceSyncRun.source_id == source_id,
                    SourceSyncRun.status.in_(ACTIVE_RUN_STATUSES),
                    SourceSyncRun.updated_at >= _stale_cutoff(),
                )
            )
        ).scalars().first()
        if active is not None:
            raise SyncAlreadyRunning(f"A sync is already {active.status} for this source.")

        context = structlog.contextvars.get_contextvars()
        run = SourceSyncRun(
            tenant_id=tenant_id, source_id=source_id, trigger=trigger, status="queued",
            triggered_by=actor_id, trace_id=context.get("trace_id"), request_id=context.get("request_id"),
        )
        session.add(run)
        await session.flush()
        return run.id


async def dispatch(container: ApplicationContainer, background_tasks: Any, source_id: UUID, run_id: UUID) -> None:
    """Hands a queued run to the worker; runs it after the response when the queue is unavailable."""
    pool = container.queue.pool()
    if pool is not None:
        await pool.enqueue_job("source_sync_job", str(source_id), str(run_id))
        return
    from packages.connectors.sync import SyncEngine

    async def _inline() -> None:
        await SyncEngine(container).run(source_id, run_id)

    background_tasks.add_task(_inline)


async def request_cancel(container: ApplicationContainer, source_id: UUID, tenant_id: UUID) -> bool:
    """Flags the source's active run for cancellation (honoured between documents)."""
    async with request_scoped_session(container) as session:
        run = (
            await session.execute(
                select(SourceSyncRun).where(
                    SourceSyncRun.source_id == source_id, SourceSyncRun.tenant_id == tenant_id, SourceSyncRun.status.in_(ACTIVE_RUN_STATUSES)
                )
            )
        ).scalars().first()
        if run is None:
            return False
        run.cancel_requested = True
        if run.status == "queued":
            run.status, run.completed_at = "cancelled", datetime.now(UTC)
        return True


async def reap_stale_runs(container: ApplicationContainer) -> int:
    """Fails runs that stopped reporting (a crashed worker), so the source can be synced again."""
    reaped = 0
    async with request_scoped_session(container) as session:
        stale = (
            await session.execute(
                select(SourceSyncRun).where(SourceSyncRun.status.in_(ACTIVE_RUN_STATUSES), SourceSyncRun.updated_at < _stale_cutoff())
            )
        ).scalars().all()
        for run in stale:
            run.status, run.completed_at = "failed", datetime.now(UTC)
            run.error_summary = "The sync stopped reporting progress (worker restarted or crashed)."
            reaped += 1
    return reaped


async def schedule_due(container: ApplicationContainer, enqueue: Any) -> int:
    """
    Queues a sync for every active, scheduled source whose time has come. `enqueue(source_id, run_id)` hands the
    run to the queue. next_sync_at moves forward immediately so a slow sync is not queued twice.
    """
    await reap_stale_runs(container)
    now = datetime.now(UTC)
    async with request_scoped_session(container) as session:
        due = (
            await session.execute(
                select(KnowledgeSource.id, KnowledgeSource.tenant_id, KnowledgeSource.sync_interval_minutes).where(
                    KnowledgeSource.status == "active",
                    KnowledgeSource.sync_mode == "scheduled",
                    KnowledgeSource.is_deleted.is_(False),
                    KnowledgeSource.next_sync_at.is_not(None),
                    KnowledgeSource.next_sync_at <= now,
                )
            )
        ).all()

    queued = 0
    for source_id, tenant_id, interval in due:
        try:
            run_id = await create_run(container, source_id, tenant_id, trigger="schedule", actor_id=None)
        except (SyncAlreadyRunning, SourceNotSyncable):
            continue
        async with request_scoped_session(container) as session:
            source = await session.get(KnowledgeSource, source_id)
            if source is not None:
                source.next_sync_at = now + timedelta(minutes=interval or 60)
        await enqueue(source_id, run_id)
        queued += 1
    if queued:
        logger.info("Scheduled source syncs queued", count=queued)
    return queued
