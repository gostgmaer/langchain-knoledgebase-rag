"""
packages/graph/nodes/researcher.py
"""

from __future__ import annotations

import asyncio

from packages.graph.schemas import ResearchFinding
from packages.graph.state import GraphState
from packages.graph.subgraphs.research import ResearchSubgraphBuilder


class ResearcherNode:
    """
    Runs the research subgraph once per decomposed sub-question, in
    parallel — reuses RetrieveNode's established asyncio.gather
    fan-out idiom (packages/graph/nodes/retrieve.py), just fanning out
    over sub-questions instead of expanded queries.
    """

    def __init__(self, research_subgraph_builder: ResearchSubgraphBuilder) -> None:
        # Compiled once at construction, mirrors GraphManager.__init__'s
        # self.graph = builder.build().
        self._subgraph = research_subgraph_builder.build()

    async def __call__(
        self,
        state: GraphState,
    ) -> GraphState:

        sub_questions = state.get("sub_questions") or []

        results = await asyncio.gather(
            *(
                self._subgraph.ainvoke(
                    {
                        "sub_question": sub_question,
                        "tenant_id": state["tenant_id"],
                        "model_profile_id": state["model_profile_id"],
                    }
                )
                for sub_question in sub_questions
            )
        )

        state["research_findings"] = [
            ResearchFinding(
                sub_question=sub_question,
                finding=result.get("finding", ""),
                citations=result.get("citations") or [],
            )
            for sub_question, result in zip(sub_questions, results, strict=True)
        ]

        return state
