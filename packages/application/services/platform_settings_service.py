# Platform settings service
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.infrastructure.repositories.platform_setting import PlatformSettingRepository

_CACHE_TTL_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class SettingSpec:
    """
    One known operational knob: its type, validation range, and built-in default.

    `default` is a plain value, not read from `packages.config.*` — these 8 keys used to be
    `.env`-configurable fields on `AppSettings`/`APISettings`/`RAGSettings`, but docs/BUGS.md item
    38's own follow-up removed that path entirely (not just added the database as an alternative):
    the database is now the *only* way to override one of these, so the fallback can't be sourced
    from an env-bindable field either — any field on a `pydantic_settings.BaseSettings` subclass
    is inherently settable via its env var by that class's own machinery, defeating the point.
    """

    key: str
    label: str
    kind: str
    """int | float | bool | string_list"""
    default: Any
    minimum: float | None = None
    maximum: float | None = None
    help: str | None = None

    def validate(self, value: Any) -> str | None:
        """Returns an error message, or None if `value` is valid for this setting."""
        if self.kind == "int":
            if isinstance(value, bool) or not isinstance(value, int):
                return f"'{self.label}' must be a whole number."
            if self.minimum is not None and value < self.minimum:
                return f"'{self.label}' must be at least {self.minimum:g}."
            if self.maximum is not None and value > self.maximum:
                return f"'{self.label}' must be at most {self.maximum:g}."
        elif self.kind == "float":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return f"'{self.label}' must be a number."
            if self.minimum is not None and value < self.minimum:
                return f"'{self.label}' must be at least {self.minimum:g}."
            if self.maximum is not None and value > self.maximum:
                return f"'{self.label}' must be at most {self.maximum:g}."
        elif self.kind == "bool":
            if not isinstance(value, bool):
                return f"'{self.label}' must be true or false."
        elif self.kind == "string_list":
            if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
                return f"'{self.label}' must be a list of non-empty text values."
        return None


# The operational knobs admins can change without a redeploy (docs/BUGS.md item 38) — rate
# limits, CORS origins, retention windows and the like. These used to double as `.env` fields
# too (a database override, env var as fallback); a follow-up removed that path, so the database
# is now the only way to change one of these — the literal below is the sole built-in default.
# Deliberately NOT here: secrets (API keys, JWT_SECRET, DB/Redis URLs — needed before this table
# is even reachable, or genuinely shouldn't live in a DB column a settings UI reads back), and
# security-boundary fields (AUTH_REQUIRED, admin_roles, tenant_override_roles) — those stay
# `.env`-only on purpose; see docs/BUGS.md item 38's own writeup for the reasoning.
SETTINGS: tuple[SettingSpec, ...] = (
    SettingSpec(
        "rate_limit_requests_per_minute", "General rate limit (requests/min)", "int",
        300, minimum=0,
        help="Per-tenant (or per-IP) cap across all routes. 0 disables it.",
    ),
    SettingSpec(
        "rate_limit_expensive_requests_per_minute", "Expensive-route rate limit (requests/min)", "int",
        60, minimum=0,
        help="Tighter cap layered on top of the general one, for /chat, /search and document uploads. 0 disables just this tighter cap.",
    ),
    SettingSpec(
        "cors_origins", "Allowed browser origins (admin app)", "string_list",
        ["http://localhost:3000", "http://127.0.0.1:3000"],
        help="Origins allowed to call this API directly from a browser (the admin frontend's own origin). Not the embeddable widget — that's per-agent, configured on the Agents page.",
    ),
    SettingSpec(
        "session_expiry_days", "Conversation session expiry (days)", "int",
        30, minimum=1,
        help="An ACTIVE conversation with no activity for this long is swept as expired.",
    ),
    SettingSpec(
        "retention_retrieval_log_days", "Retrieval log retention (days)", "int",
        90, minimum=0,
        help="Retrieval logs older than this are purged. 0 keeps them forever.",
    ),
    SettingSpec(
        "retention_audit_days", "Audit trail retention (days)", "int",
        365, minimum=0,
        help="Audit events older than this are purged. 0 keeps them forever.",
    ),
    SettingSpec(
        "reindex_stale_after_days", "Re-index documents after (days)", "int",
        90, minimum=1,
        help="A document not re-embedded in this many days becomes a candidate for the weekly re-index sweep.",
    ),
    SettingSpec(
        "connector_sync_concurrency", "Knowledge source sync concurrency", "int",
        4, minimum=1, maximum=16,
        help="How many documents a single source sync processes in flight at once.",
    ),
    SettingSpec(
        "rag_context_token_budget", "Retrieved context token budget", "int",
        4000, minimum=1,
        help="Max tokens of retrieved chunks folded into one prompt; de-duped context beyond this is dropped, not truncated mid-chunk.",
    ),
    SettingSpec(
        "retrieval_keyword_weight", "Hybrid search keyword weight", "float",
        1.0, minimum=0.0, maximum=2.0,
        help="Weight given to BM25 keyword matches in reciprocal rank fusion, relative to vector search (fixed at 1.0). Higher favors exact-term matches.",
    ),
)

_SPEC_BY_KEY: dict[str, SettingSpec] = {spec.key: spec for spec in SETTINGS}


def default_value(key: str) -> Any:
    """A known setting's built-in default, for the rare caller with no container to read
    `PlatformSettingsService` from at all (packages/application/services/retention_service.py's
    `purge_expired`, when nothing passes it an explicit value — e.g. a test)."""
    return _SPEC_BY_KEY[key].default


class PlatformSettingsService:
    """
    Dynamic (no-redeploy) reads of the operational knobs in `SETTINGS`, backed by Postgres with
    a short in-process TTL cache — same shape and reasoning as `FeatureFlagService` (an
    in-process dict, not Redis: eventual ~30s consistency across replicas is an accepted
    trade-off here, same as that service's own). Takes a raw `session_factory` rather than a
    request-scoped repository for the same reason: callers like `RateLimitMiddleware` run before
    this app's usual per-request session exists.
    """

    def __init__(self, session_factory: Callable[[], AsyncSession] | async_sessionmaker) -> None:
        self._session_factory = session_factory
        self._cache: dict[str, tuple[Any, float]] = {}

    async def get(self, key: str) -> Any:
        spec = _SPEC_BY_KEY[key]

        cached = self._cache.get(key)
        if cached is not None and (time.monotonic() - cached[1]) < _CACHE_TTL_SECONDS:
            return cached[0]

        async with self._session_factory() as session:
            repo = PlatformSettingRepository(session)
            row = await repo.get_by_key(key)

        # A copy for a list default (cors_origins): SettingSpec is frozen, but that doesn't deep-
        # freeze a contained list — returning the registry's own list would let a caller's in-place
        # mutation corrupt the built-in default for every future read, for the rest of the process.
        value = row.value if row is not None else (list(spec.default) if isinstance(spec.default, list) else spec.default)
        self._cache[key] = (value, time.monotonic())
        return value

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)

    async def effective_values(self) -> dict[str, Any]:
        """Every known setting's current effective value, in one pass."""
        return {spec.key: await self.get(spec.key) for spec in SETTINGS}

    async def seed_defaults(self) -> None:
        """
        Writes an explicit row for every `SETTINGS` key that has none yet, so
        `platform_settings` is never empty after first boot and an admin opening the page sees
        every current value as a real row, not an absence. Called once from
        `packages/api/lifespan.py` at startup; idempotent — only inserts missing keys, never
        touches a row that already exists (including one an admin already overrode).

        Deliberate trade-off, confirmed with the user over the alternative (no seeding, `.get()`'s
        "no row = whatever the code's built-in default is today" behavior, which is the service's
        own long-standing default): once a row exists here, a future release that changes a
        built-in default will NOT reach an installation that already ran this seed — the stored
        row keeps returning today's value until an admin explicitly resets that key.
        """
        from packages.domain.models.platform_setting import PlatformSetting

        async with self._session_factory() as session:
            repo = PlatformSettingRepository(session)
            seeded_keys: list[str] = []
            for spec in SETTINGS:
                existing = await repo.get_by_key(spec.key)
                if existing is None:
                    value = list(spec.default) if isinstance(spec.default, list) else spec.default
                    session.add(PlatformSetting(key=spec.key, value=value, updated_by=None))
                    seeded_keys.append(spec.key)
            if seeded_keys:
                await session.commit()

        for key in seeded_keys:
            self.invalidate(key)

    async def set(self, key: str, value: Any, *, updated_by: UUID | None) -> None:
        """`value=None` reverts the key to its built-in default (deletes the override row)."""
        from packages.domain.models.platform_setting import PlatformSetting

        async with self._session_factory() as session:
            repo = PlatformSettingRepository(session)
            row = await repo.get_by_key(key)
            if value is None:
                if row is not None:
                    await session.delete(row)
                    await session.commit()
            elif row is not None:
                row.value = value
                row.updated_by = updated_by
                await session.commit()
            else:
                session.add(PlatformSetting(key=key, value=value, updated_by=updated_by))
                await session.commit()

        self.invalidate(key)
