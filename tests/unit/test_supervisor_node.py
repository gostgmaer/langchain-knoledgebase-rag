"""
SupervisorNode (packages/graph/nodes/supervisor.py) — the hard
fail-open guarantee protecting the entire existing single-question
path: an LLM exception AND a nonsensical is_multi_part=True with zero
sub_questions must both collapse to is_multi_part=False.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from packages.graph.nodes.supervisor import SubQuestionPlan, SupervisorNode


class _FakeChain:
    def __init__(self, *, result=None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error

    async def ainvoke(self, _prompt: str):
        if self._error is not None:
            raise self._error
        return self._result


class _FakeLLM:
    def __init__(self, chain: _FakeChain) -> None:
        self._chain = chain

    def with_structured_output(self, _schema):
        return self._chain


def _state(query: str = "compare our approach to X across these documents") -> dict:
    return {"messages": [HumanMessage(content=query)]}


@pytest.mark.asyncio
async def test_llm_error_fails_open_to_non_multi_part():
    node = SupervisorNode(_FakeLLM(_FakeChain(error=RuntimeError("provider down"))))

    result = await node(_state())

    assert result["is_multi_part"] is False
    assert result["sub_questions"] == []


@pytest.mark.asyncio
async def test_multi_part_true_with_no_sub_questions_is_treated_as_non_multi_part():
    """
    The hard guarantee, not just the try/except: a response claiming
    is_multi_part=True but supplying nothing to research must never
    route into Researcher with nothing to research.
    """
    plan = SubQuestionPlan(is_multi_part=True, sub_questions=[])
    node = SupervisorNode(_FakeLLM(_FakeChain(result=plan)))

    result = await node(_state())

    assert result["is_multi_part"] is False
    assert result["sub_questions"] == []


@pytest.mark.asyncio
async def test_genuine_multi_part_decomposition_is_passed_through():
    plan = SubQuestionPlan(
        is_multi_part=True,
        sub_questions=["What does document A say about X?", "What does document B say about X?"],
    )
    node = SupervisorNode(_FakeLLM(_FakeChain(result=plan)))

    result = await node(_state())

    assert result["is_multi_part"] is True
    assert result["sub_questions"] == plan.sub_questions


@pytest.mark.asyncio
async def test_non_multi_part_response_clears_sub_questions():
    plan = SubQuestionPlan(is_multi_part=False, sub_questions=[])
    node = SupervisorNode(_FakeLLM(_FakeChain(result=plan)))

    result = await node(_state("what's the capital of France?"))

    assert result["is_multi_part"] is False
    assert result["sub_questions"] == []


@pytest.mark.asyncio
async def test_returns_only_its_own_keys_not_the_whole_mutated_state():
    """
    docs/BUGS.md item 61 — this node now fans out from START alongside
    `load_memory` in the same superstep (GraphBuilder's
    START -> {planner, load_memory, supervisor} -> join). Returning the
    full `state` object, rather than a scoped partial dict, makes
    LangGraph treat it as a write to every key in `state` — including
    "memories", which `load_memory` is writing concurrently in that
    exact same step — and LangGraph's LastValue channels fatally reject
    two writers to one channel in a single step. This must return only
    its own two keys, no matter what else is sitting in `state`.
    """
    plan = SubQuestionPlan(is_multi_part=False, sub_questions=[])
    node = SupervisorNode(_FakeLLM(_FakeChain(result=plan)))

    state = _state()
    state["memories"] = []
    state["execution_plan"] = object()

    result = await node(state)

    assert set(result.keys()) == {"is_multi_part", "sub_questions"}
