"""
The one piece of docs/BUGS.md item 37 (the public embeddable chat widget) that would be a real
security hole if it regressed: an anonymous website visitor must never get the IAM lookup tools,
web search, or a tenant's CUSTOM webhook tools, only knowledge-base search and the calculator.
packages/infrastructure/container/tools.py's init_tool_manager is where that's enforced — this
test calls it directly with widget mode on and off and asserts the registered tool set differs
exactly as the allowlist (not denylist) design intends.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from packages.infrastructure.container.tools import init_tool_manager
from packages.tools.context import set_custom_tools, set_widget_mode
from packages.tools.executor import ToolExecutor
from packages.tools.registry import ToolRegistry

ALWAYS_ON = {"search_knowledge_base", "search_document", "calculator"}
WIDGET_FORBIDDEN = {"lookup_iam_user", "lookup_iam_tenant", "get_weather", "get_news", "get_google_search"}


def _build(*, widget: bool, custom_tool_names: tuple[str, ...] = ()) -> set[str]:
    set_widget_mode(widget)
    custom = []
    for name in custom_tool_names:
        fake = MagicMock()
        fake.name = name
        custom.append(fake)
    set_custom_tools(custom)
    try:
        registry = ToolRegistry()
        manager = init_tool_manager(
            registry=registry,
            executor=ToolExecutor(registry),
            knowledge_manager=MagicMock(),
            iam_client=MagicMock(),
        )
        return {t.name for t in manager.list()}
    finally:
        set_widget_mode(False)
        set_custom_tools([])


@pytest.fixture(autouse=True)
def _reset_context():
    yield
    set_widget_mode(False)
    set_custom_tools([])


def test_authenticated_chat_gets_every_builtin_tool():
    names = _build(widget=False)
    assert ALWAYS_ON <= names
    assert WIDGET_FORBIDDEN <= names


def test_widget_mode_gets_only_the_safe_allowlist():
    names = _build(widget=True)
    assert names == ALWAYS_ON  # exact set, not just "at least" — a new builtin tool defaults OUT


def test_widget_mode_never_registers_a_tenants_custom_webhook_tools():
    names = _build(widget=True, custom_tool_names=("internal_billing_webhook",))
    assert "internal_billing_webhook" not in names


def test_authenticated_chat_still_registers_custom_webhook_tools():
    names = _build(widget=False, custom_tool_names=("internal_billing_webhook",))
    assert "internal_billing_webhook" in names
