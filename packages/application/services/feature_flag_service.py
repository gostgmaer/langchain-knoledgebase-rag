from __future__ import annotations

import time
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.infrastructure.repositories.feature_flag import FeatureFlagRepository
from packages.shared.logging import get_logger

logger = get_logger(__name__)

_CACHE_TTL_SECONDS = 30.0

# Seeded only with today's one real consumer (see
# packages/api/dependencies.py's require_permission/require_role) —
# matching FeatureSettings.enable_rbac's current static default. The
# other 10 flags declared in packages/config/features.py have no
# runtime gating logic anywhere to look up a dynamic value for, so
# they're deliberately not seeded here.
_STATIC_DEFAULTS: dict[str, bool] = {
    "enable_rbac": False,
}


class FeatureFlagService:
    """
    Dynamic (no-redeploy) feature flag reads, backed by Postgres with
    a short in-process TTL cache — unlike the static
    `packages/config/features.py::FeatureSettings` (baked into one
    `providers.Object` at container-build time), this can change
    while the app is running.

    Takes a raw `async_sessionmaker` rather than a request-scoped
    `FeatureFlagRepository` because this needs to be callable from
    `require_permission`/`require_role`, which run as a FastAPI
    dependency before this app's usual `request_scoped_session`
    context exists for the request — it opens its own short-lived
    session per cache-miss instead of reusing the ContextVar-bound one.
    """

    def __init__(self, session_factory: Callable[[], AsyncSession] | async_sessionmaker) -> None:
        self._session_factory = session_factory
        self._cache: dict[tuple[str, str], tuple[bool, float]] = {}

    async def get_effective(self, key: str, tenant_id: UUID | None) -> bool:
        cache_key = (key, str(tenant_id))
        cached = self._cache.get(cache_key)

        if cached is not None and (time.monotonic() - cached[1]) < _CACHE_TTL_SECONDS:
            return cached[0]

        async with self._session_factory() as session:
            repo = FeatureFlagRepository(session)
            value = await repo.get_effective(key, tenant_id)

        result = value if value is not None else _STATIC_DEFAULTS.get(key, False)

        self._cache[cache_key] = (result, time.monotonic())

        return result

    def invalidate(self, key: str, tenant_id: UUID | None = None) -> None:
        """
        Called after a toggle write so the next read doesn't serve a
        stale cached value for up to 30s.

        A tenant-override write only ever affects that one tenant's
        cache entry. A *global* write (tenant_id=None) can change the
        effective value for every tenant that has no override of its
        own — and the cache has no record of which tenant_ids have
        actually read this key, so the only correct fix is dropping
        every cached entry for this key, not guessing a single one
        (confirmed live: guessing `(key, str(None))` left the real
        per-tenant-keyed entry — e.g. `(key, str(DEFAULT_TENANT_ID))`
        — stale for the rest of its TTL).
        """
        if tenant_id is not None:
            self._cache.pop((key, str(tenant_id)), None)
            return

        for cache_key in [k for k in self._cache if k[0] == key]:
            del self._cache[cache_key]
