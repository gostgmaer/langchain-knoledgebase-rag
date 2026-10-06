"""
Carries one request's tenant-specific CUSTOM webhook tools (packages/tools/webhook.py,
docs/BUGS.md item 29) from where they're built (the chat router, `async`, with a real DB session)
to `init_tool_manager` (packages/infrastructure/container/tools.py), which must stay a plain sync
function: it sits behind `ApplicationContainer`'s single, process-wide `providers.Factory` chain
(packages/infrastructure/container/graph.py builds the whole LangGraph graph — nodes, LLM binding,
the works — synchronously), and making any one provider in that chain async would force every
caller of `container.graph.*` across the app to `await` it, a blast radius far bigger than this one
feature. A ContextVar sidesteps that entirely: the router does the async DB work up front and drops
the *already-built* tool objects here; the sync factory just reads them back.

A plain Python list, not a repository/session reference — the DB session this was built with may
already be gone by the time something reads it back.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING
from uuid import UUID

from langchain_core.tools import BaseTool

if TYPE_CHECKING:
    from packages.application.services.feature_flag_service import FeatureFlagService

_custom_tools: ContextVar[list[BaseTool] | None] = ContextVar("custom_webhook_tools", default=None)

# Set by the public widget router (packages/api/routers/widget.py) before every request, never by
# anything authenticated. An anonymous website visitor gets knowledge-base search and the
# calculator only — never lookup_iam_user/lookup_iam_tenant (internal data, not public visitors'
# to query) or a tenant's CUSTOM webhook tools (may reach internal systems never meant to be
# reachable from the public internet). This is an allowlist, not a denylist, on purpose: a new
# builtin tool added later is excluded from the widget by default until someone decides otherwise.
_widget_mode: ContextVar[bool] = ContextVar("widget_mode", default=False)

# Which of the four Feature-Flag-gated builtin tools (get_google_search, get_weather, get_news,
# calculator — packages/infrastructure/container/tools.py's init_tool_manager) this request may
# register, pre-fetched from FeatureFlagService the same way set_custom_tools's tools are: the
# router does the async DB/cache read up front, the sync factory just reads it back. `None` (the
# default) means "never fetched" and is treated as "everything enabled" — fail open, same
# reasoning as this app's IAM auth and rate limiter, so a code path that forgets to call
# set_enabled_tools doesn't silently lose a tool instead of erroring loudly in a test.
_enabled_tools: ContextVar[frozenset[str] | None] = ContextVar("enabled_builtin_tools", default=None)


def set_custom_tools(tools: list[BaseTool]) -> None:
    _custom_tools.set(tools)


def current_custom_tools() -> list[BaseTool]:
    # No shared mutable default (ContextVar(default=[]) would be one list reused across every
    # context that never called set_custom_tools) — a fresh empty list per call instead.
    return _custom_tools.get() or []


def set_widget_mode(enabled: bool) -> None:
    _widget_mode.set(enabled)


def is_widget_mode() -> bool:
    return _widget_mode.get()


def set_enabled_tools(names: frozenset[str]) -> None:
    _enabled_tools.set(names)


def reset_enabled_tools() -> None:
    """Back to the true default (`None` — fail open), not an empty set (everything disabled) —
    tests that touch `set_enabled_tools` must use this for teardown, not
    `set_enabled_tools(frozenset())`, which leaks a "nothing enabled" state into whatever runs
    next in the same interpreter (ContextVars aren't test-isolated unless something resets them;
    confirmed live, exactly this way, by docs/BUGS.md item 38's own test suite)."""
    _enabled_tools.set(None)


def is_tool_enabled(name: str) -> bool:
    enabled = _enabled_tools.get()
    return True if enabled is None else name in enabled


_FLAG_TO_TOOL: dict[str, str] = {
    "enable_calculator": "calculator",
    "enable_web_search": "get_google_search",
    "enable_weather": "get_weather",
    "enable_news": "get_news",
}


async def fetch_enabled_tools(feature_flags: FeatureFlagService, tenant_id: UUID | None) -> frozenset[str]:
    """
    The async half of set_enabled_tools/is_tool_enabled's pair — call this from a router (real DB
    session, can await) and pass the result to set_enabled_tools before building the graph.
    """
    enabled = {name for flag_key, name in _FLAG_TO_TOOL.items() if await feature_flags.get_effective(flag_key, tenant_id)}
    return frozenset(enabled)
