from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from packages.graph.state import GraphState


class NextNode(StrEnum):
    LLM = "llm"
    RETRIEVE = "retrieve"
    TOOL = "tool"


RETRIEVAL_KEYWORDS = (
    "search",
    "find",
    "lookup",
    "document",
    "knowledge",
    "manual",
    "policy",
    "wiki",
    "rag",
    
)


@dataclass(slots=True)
class PlannerResult:
    next_node: NextNode
    reason: str


class GraphPlanner:

    async def plan(
        self,
        state: GraphState,
    ) -> PlannerResult:

        message = state["messages"][-1].content.lower()

        if any(keyword in message for keyword in RETRIEVAL_KEYWORDS):
            return PlannerResult(
                next_node=NextNode.RETRIEVE,
                reason="Retrieval keyword detected.",
            )

        return PlannerResult(
            next_node=NextNode.LLM,
            reason="Direct LLM response.",
        )