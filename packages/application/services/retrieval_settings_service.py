# Retrieval settings service
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.config.loader import settings
from packages.domain.models.retrieval_settings import RetrievalSettings
from packages.shared.logging import get_logger

logger = get_logger(__name__)

_CACHE_TTL_SECONDS = 30.0

# Bounds enforced on write (the API validates the same limits).
MAX_RESULTS_RANGE = (1, 20)
MIN_RELEVANCE_RANGE = (-10.0, 10.0)


@dataclass(frozen=True, slots=True)
class EffectiveRetrievalSettings:
    max_results: int
    min_relevance_score: float
    reranking_enabled: bool


@dataclass(frozen=True, slots=True)
class RetrievalOverrides:
    max_results: int | None = None
    min_relevance_score: float | None = None
    reranking_enabled: bool | None = None


def platform_defaults() -> EffectiveRetrievalSettings:
    """The environment-configured values every tenant gets unless it overrides them."""
    return EffectiveRetrievalSettings(
        max_results=settings.rag.max_results,
        min_relevance_score=settings.rag.min_relevance_score,
        reranking_enabled=settings.features.enable_reranking,
    )


def merge(overrides: RetrievalOverrides) -> EffectiveRetrievalSettings:
    base = platform_defaults()
    return EffectiveRetrievalSettings(
        max_results=overrides.max_results if overrides.max_results is not None else base.max_results,
        min_relevance_score=(
            overrides.min_relevance_score if overrides.min_relevance_score is not None else base.min_relevance_score
        ),
        reranking_enabled=(
            overrides.reranking_enabled if overrides.reranking_enabled is not None else base.reranking_enabled
        ),
    )


class RetrievalSettingsService:
    """
    Reads and writes a tenant's retrieval overrides. Takes a raw session factory (like the other
    process-wide services) so it never shares a request's transaction, and caches reads for a
    short TTL because retrieval asks on every question. A read failure falls back to the
    platform defaults: settings must never be able to break answering.
    """

    def __init__(self, session_factory: Callable[[], AsyncSession] | async_sessionmaker) -> None:
        self._session_factory = session_factory
        self._cache: dict[UUID, tuple[float, RetrievalOverrides]] = {}

    def invalidate(self, tenant_id: UUID) -> None:
        self._cache.pop(tenant_id, None)

    async def get_overrides(self, tenant_id: UUID) -> RetrievalOverrides:
        cached = self._cache.get(tenant_id)
        if cached and time.monotonic() - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]

        try:
            async with self._session_factory() as session:
                row = (
                    await session.execute(select(RetrievalSettings).where(RetrievalSettings.tenant_id == tenant_id))
                ).scalar_one_or_none()
            overrides = (
                RetrievalOverrides(row.max_results, row.min_relevance_score, row.reranking_enabled)
                if row is not None
                else RetrievalOverrides()
            )
        except Exception as exc:  # noqa: BLE001 - never let settings break retrieval
            logger.warning("Could not read retrieval settings, using defaults", error=str(exc))
            return RetrievalOverrides()

        self._cache[tenant_id] = (time.monotonic(), overrides)
        return overrides

    async def get_effective(self, tenant_id: UUID) -> EffectiveRetrievalSettings:
        return merge(await self.get_overrides(tenant_id))

    async def save(
        self,
        tenant_id: UUID,
        overrides: RetrievalOverrides,
        updated_by: UUID | None,
    ) -> RetrievalOverrides:
        """Replaces the tenant's overrides (None fields fall back to the platform default)."""
        async with self._session_factory() as session:
            row = (
                await session.execute(select(RetrievalSettings).where(RetrievalSettings.tenant_id == tenant_id))
            ).scalar_one_or_none()
            if row is None:
                row = RetrievalSettings(tenant_id=tenant_id)
                session.add(row)
            row.max_results = overrides.max_results
            row.min_relevance_score = overrides.min_relevance_score
            row.reranking_enabled = overrides.reranking_enabled
            row.updated_by = updated_by
            await session.commit()

        self.invalidate(tenant_id)
        return overrides
