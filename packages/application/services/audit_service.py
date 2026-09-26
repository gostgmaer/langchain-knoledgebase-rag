# Audit service
from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.domain.models.audit_event import AuditEvent
from packages.shared.logging import get_logger

logger = get_logger(__name__)

# Keys that must never be written into an audit event, whatever a caller passes.
_FORBIDDEN_KEYS = {"password", "token", "secret", "api_key", "authorization", "content", "query"}


def clean_detail(detail: dict[str, Any] | None) -> dict[str, Any]:
    """Drops anything that looks like a secret or document/query content."""
    return {k: v for k, v in (detail or {}).items() if k.lower() not in _FORBIDDEN_KEYS}


class AuditService:
    """
    Writes append-only audit events in their own transaction (like RetrievalLogService), so an
    audit write neither joins nor poisons the request's transaction. Best-effort: a failure is
    reported and swallowed rather than failing the operation being audited.
    """

    def __init__(self, session_factory: Callable[[], AsyncSession] | async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def record(
        self,
        *,
        tenant_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        actor_id: UUID | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        request_id = structlog.contextvars.get_contextvars().get("request_id")
        try:
            async with self._session_factory() as session:
                session.add(
                    AuditEvent(
                        tenant_id=tenant_id,
                        actor_id=actor_id,
                        action=action,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        request_id=request_id,
                        detail=clean_detail(detail),
                    )
                )
                await session.commit()
        except Exception as exc:  # noqa: BLE001 - auditing must not break the operation
            logger.warning("Could not persist audit event", action=action, error=str(exc))
