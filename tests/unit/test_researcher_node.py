"""
ResearcherNode (packages/graph/nodes/researcher.py) — parallel
fan-out over sub_questions via the compiled research subgraph, mirrors
RetrieveNode's own asyncio.gather idiom. No real subgraph execution —
a fake subgraph builder/compiled graph.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from packages.graph.nodes.researcher import ResearcherNode


class _FakeCompiledSubgraph:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def ainvoke(self, sub_state: dict) -> dict:
        self.calls.append(sub_state)
        return {
            "finding": f"finding for: {sub_state['sub_question']}",
            "citations": [],
        }


class _FakeSubgraphBuilder:
    def __init__(self, compiled: _FakeCompiledSubgraph) -> None:
        self._compiled = compiled

    def build(self):
        return self._compiled


@pytest.mark.asyncio
async def test_invokes_the_subgraph_once_per_sub_question_in_parallel():
    compiled = _FakeCompiledSubgraph()
    node = ResearcherNode(_FakeSubgraphBuilder(compiled))

    sub_questions = ["What does A say?", "What does B say?", "What does C say?"]
    state = {
        "sub_questions": sub_questions,
        "tenant_id": uuid4(),
        "model_profile_id": uuid4(),
    }

    result = await node(state)

    assert len(compiled.calls) == len(sub_questions)
    assert result["research_findings"][0].sub_question == sub_questions[0]
    assert result["research_findings"][0].finding == f"finding for: {sub_questions[0]}"
    assert [f.sub_question for f in result["research_findings"]] == sub_questions


@pytest.mark.asyncio
async def test_no_sub_questions_produces_no_findings_without_invoking_the_subgraph():
    compiled = _FakeCompiledSubgraph()
    node = ResearcherNode(_FakeSubgraphBuilder(compiled))

    result = await node({"sub_questions": [], "tenant_id": uuid4(), "model_profile_id": uuid4()})

    assert result["research_findings"] == []
    assert compiled.calls == []
