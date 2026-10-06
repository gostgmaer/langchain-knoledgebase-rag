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

from langchain_core.tools import BaseTool

_custom_tools: ContextVar[list[BaseTool] | None] = ContextVar("custom_webhook_tools", default=None)

# Set by the public widget router (packages/api/routers/widget.py) before every request, never by
# anything authenticated. An anonymous website visitor gets knowledge-base search and the
# calculator only — never lookup_iam_user/lookup_iam_tenant (internal data, not public visitors'
# to query) or a tenant's CUSTOM webhook tools (may reach internal systems never meant to be
# reachable from the public internet). This is an allowlist, not a denylist, on purpose: a new
# builtin tool added later is excluded from the widget by default until someone decides otherwise.
_widget_mode: ContextVar[bool] = ContextVar("widget_mode", default=False)


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
