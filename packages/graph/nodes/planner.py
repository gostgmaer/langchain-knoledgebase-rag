from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from typing import TYPE_CHECKING

if TYPE_CHECKING:
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

    async def __call__(
        self,
        state: GraphState,
    ) -> dict:

        message = state["messages"][-1].content.lower()

        if any(keyword in message for keyword in RETRIEVAL_KEYWORDS):
            return {
                "execution_plan": PlannerResult(
                    next_node=NextNode.RETRIEVE,
                    reason="Retrieval keyword detected.",
                )
            }

        return {
            "execution_plan": PlannerResult(
                next_node=NextNode.LLM,
                reason="Direct LLM response.",
            )
        }