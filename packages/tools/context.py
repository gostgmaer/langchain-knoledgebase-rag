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


def set_custom_tools(tools: list[BaseTool]) -> None:
    _custom_tools.set(tools)


def current_custom_tools() -> list[BaseTool]:
    # No shared mutable default (ContextVar(default=[]) would be one list reused across every
    # context that never called set_custom_tools) — a fresh empty list per call instead.
    return _custom_tools.get() or []
