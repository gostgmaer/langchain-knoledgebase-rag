"""
Per-request access clearance, readable anywhere below the request without threading arguments.

`can_read_restricted()` defaults to False: any code path that runs outside an authenticated request
(a worker job, a script, a test) sees only unrestricted documents. The authentication middleware
raises it to True for administrators (and for anonymous development mode when AUTH_REQUIRED is off).
"""

from __future__ import annotations

from contextvars import ContextVar, Token

_can_read_restricted: ContextVar[bool] = ContextVar("can_read_restricted", default=False)


def can_read_restricted() -> bool:
    return _can_read_restricted.get()


def set_can_read_restricted(value: bool) -> Token:
    return _can_read_restricted.set(value)


_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)
_user_roles: ContextVar[tuple[str, ...]] = ContextVar("current_user_roles", default=())
_retrieval_filters: ContextVar[dict] = ContextVar("retrieval_filters", default={})

FILTER_KEYS = ("document_types", "categories", "tags", "language", "source_types", "source_ids")


def current_user_id() -> str | None:
    return _user_id.get()


def current_user_roles() -> tuple[str, ...]:
    return _user_roles.get()


def set_user(user_id: str | None, roles: list[str] | tuple[str, ...]) -> None:
    """Records who the current request acts as, for document-level (role / user) access checks."""
    _user_id.set(user_id)
    _user_roles.set(tuple(roles))


def set_retrieval_filters(filters: dict | None) -> None:
    """Metadata filters the caller asked for (chat). Unknown keys and empty values are dropped."""
    _retrieval_filters.set({k: v for k, v in (filters or {}).items() if k in FILTER_KEYS and v})


def retrieval_filters() -> dict:
    return dict(_retrieval_filters.get())


# `retrieval_strategy` (docs/BUGS.md item 38 follow-up) moved from a static `.env` field
# (packages/config/rag.py) to Platform Settings, read fresh per request — but
# `RetrieverFactory.create` (packages/knowledge/retrievers/factory.py) sits behind
# `ApplicationContainer`'s plain-sync `providers.Factory` chain, same impasse
# packages/tools/context.py's own docstring describes for custom tools: making any one provider
# in that chain async would force every caller of `container.rag.*`/`container.graph.*` to
# `await` it. Same fix: the router does the async `PlatformSettingsService.get()` read up front
# and drops the already-fetched string here; the sync factory just reads it back. `None` (never
# fetched — a worker job, a script, a test) falls back to "hybrid", this app's long-standing
# static default, not a crash.
_retrieval_strategy: ContextVar[str | None] = ContextVar("retrieval_strategy", default=None)


def set_retrieval_strategy(strategy: str | None) -> None:
    _retrieval_strategy.set(strategy)


def current_retrieval_strategy() -> str:
    return _retrieval_strategy.get() or "hybrid"
