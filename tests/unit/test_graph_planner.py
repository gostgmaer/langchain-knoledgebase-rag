"""
GraphPlanner (packages/planner/planner.py) — retrieval always runs
(docs/BUGS.md item 57), and as of item 63 this node also decides
is_multi_part itself, folded into the same QueryAnalyzer call instead
of a second concurrent LLM round-trip (the now-deleted SupervisorNode).
Carries forward SupervisorNode's exact hard fail-open guarantee: an
analyzer error, a missing analyzer, or a nonsensical
is_multi_part=True with zero sub_questions must all collapse to
is_multi_part=False — this must never crash and must never route into
Researcher with nothing to research.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from packages.planner.models import Capability
from packages.planner.planner import GraphPlanner
from packages.planner.query_analyzer import QueryAnalysis


class _FakeAnalyzer:
    def __init__(self, *, result: QueryAnalysis | None = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error

    async def analyze(self, _messages):
        if self._error is not None:
            raise self._error
        return self._result


def _state(query: str = "compare our approach to X across these documents") -> dict:
    return {"messages": [HumanMessage(content=query)]}


@pytest.mark.asyncio
async def test_retrieval_always_runs_even_without_an_analyzer():
    node = GraphPlanner(query_analyzer=None)

    result = await node(_state())

    assert result["execution_plan"].has(Capability.RETRIEVAL)


@pytest.mark.asyncio
async def test_no_analyzer_configured_fails_open_to_non_multi_part():
    node = GraphPlanner(query_analyzer=None)

    result = await node(_state())

    assert result["is_multi_part"] is False
    assert result["sub_questions"] == []


@pytest.mark.asyncio
async def test_analyzer_error_fails_open_to_non_multi_part_and_retrieval_still_runs():
    node = GraphPlanner(query_analyzer=_FakeAnalyzer(error=RuntimeError("provider down")))

    result = await node(_state())

    assert result["is_multi_part"] is False
    assert result["sub_questions"] == []
    assert result["execution_plan"].has(Capability.RETRIEVAL)


@pytest.mark.asyncio
async def test_multi_part_true_with_no_sub_questions_is_treated_as_non_multi_part():
    """
    The hard guarantee, not just the try/except: a response claiming
    is_multi_part=True but supplying nothing to research must never
    route into Researcher with nothing to research.
    """
    analysis = QueryAnalysis(rewritten_query="q", is_multi_part=True, sub_questions=[])
    node = GraphPlanner(query_analyzer=_FakeAnalyzer(result=analysis))

    result = await node(_state())

    assert result["is_multi_part"] is False
    assert result["sub_questions"] == []


@pytest.mark.asyncio
async def test_genuine_multi_part_decomposition_is_passed_through():
    analysis = QueryAnalysis(
        rewritten_query="compare A and B on X",
        is_multi_part=True,
        sub_questions=["What does document A say about X?", "What does document B say about X?"],
    )
    node = GraphPlanner(query_analyzer=_FakeAnalyzer(result=analysis))

    result = await node(_state())

    assert result["is_multi_part"] is True
    assert result["sub_questions"] == analysis.sub_questions
    assert result["rewritten_query"] == "compare A and B on X"


@pytest.mark.asyncio
async def test_non_multi_part_response_clears_sub_questions_and_sets_rewrite():
    analysis = QueryAnalysis(
        rewritten_query="what's the capital of France?",
        expanded_queries=["capital city of France"],
        is_multi_part=False,
        sub_questions=[],
    )
    node = GraphPlanner(query_analyzer=_FakeAnalyzer(result=analysis))

    result = await node(_state("what's the capital of France?"))

    assert result["is_multi_part"] is False
    assert result["sub_questions"] == []
    assert result["rewritten_query"] == "what's the capital of France?"
    assert result["expanded_queries"] == ["capital city of France"]


@pytest.mark.asyncio
async def test_returns_only_a_scoped_partial_dict_not_the_whole_state():
    """
    This node fans out from START alongside load_memory in the same
    superstep (GraphBuilder's START -> {planner, load_memory} -> join).
    Returning the full `state` object, rather than a scoped partial
    dict, would make LangGraph treat it as a write to every key in
    `state` — the exact class of bug item 61 fixed for the (now
    deleted) SupervisorNode. Guards against ever reintroducing it here.
    """
    analysis = QueryAnalysis(rewritten_query="q", is_multi_part=False, sub_questions=[])
    node = GraphPlanner(query_analyzer=_FakeAnalyzer(result=analysis))

    state = _state()
    state["memories"] = []
    state["some_other_key"] = object()

    result = await node(state)

    assert "memories" not in result
    assert "some_other_key" not in result
