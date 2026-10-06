"""
docs/BUGS.md item 38: enable_calculator/enable_web_search/enable_weather/enable_news moved from
static, dead `packages/config/features.py` booleans (confirmed live: grepping the whole codebase
for each name found zero consumers before this change) to real Feature Flags gating
init_tool_manager's registration of each corresponding builtin tool — the same dynamic,
no-redeploy pattern enable_rbac already used. This covers the sync half (init_tool_manager +
packages/tools/context.py's is_tool_enabled); tests/api/test_platform_settings_api.py and
test_feature_flags_api.py cover the API surface each flag/setting is changed through.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from packages.infrastructure.container.tools import init_tool_manager
from packages.tools.context import reset_enabled_tools, set_enabled_tools, set_widget_mode
from packages.tools.executor import ToolExecutor
from packages.tools.registry import ToolRegistry


def _build() -> set[str]:
    registry = ToolRegistry()
    manager = init_tool_manager(
        registry=registry,
        executor=ToolExecutor(registry),
        knowledge_manager=MagicMock(),
        iam_client=MagicMock(),
    )
    return {t.name for t in manager.list()}


@pytest.fixture(autouse=True)
def _reset_context():
    yield
    reset_enabled_tools()
    set_widget_mode(False)


def test_a_request_that_never_fetched_flags_gets_every_tool_fail_open():
    # set_enabled_tools never called this test: is_tool_enabled's None-means-everything-on default.
    names = _build()
    assert {"calculator", "get_weather", "get_news", "get_google_search"} <= names


def test_each_flag_gates_exactly_its_own_tool():
    set_enabled_tools(frozenset({"calculator", "get_news"}))  # weather and search off
    names = _build()
    assert "calculator" in names
    assert "get_news" in names
    assert "get_weather" not in names
    assert "get_google_search" not in names
    # Never gated by these flags — always present regardless of the enabled-tools set.
    assert "search_knowledge_base" in names
    assert "lookup_iam_user" in names


def test_all_four_off_still_leaves_knowledge_base_search_and_iam_tools():
    set_enabled_tools(frozenset())
    names = _build()
    assert names & {"calculator", "get_weather", "get_news", "get_google_search"} == set()
    assert {"search_knowledge_base", "search_document", "lookup_iam_user", "lookup_iam_tenant"} <= names


def test_calculator_flag_also_applies_inside_widget_mode():
    """The widget's own allowlist (docs/BUGS.md item 37) includes the calculator — an admin who's
    disabled it platform-wide should see that honoured there too, not just on /chat."""
    set_widget_mode(True)
    set_enabled_tools(frozenset())  # calculator disabled
    assert "calculator" not in _build()

    set_enabled_tools(frozenset({"calculator"}))
    assert "calculator" in _build()
