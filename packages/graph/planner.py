from __future__ import annotations

from dataclasses import dataclass

from packages.graph.state import GraphState

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
    next_node: str


class GraphPlanner:

    async def plan(
        self,
        state,
    ) -> PlannerResult:

        message = state["messages"][-1].content.lower()

        #
        # Temporary rules
        #

        # if "weather" in message:
        #     return PlannerResult("tool")

        print(f"[GraphPlanner] Evaluating message: {message}")
        if any(keyword in message for keyword in RETRIEVAL_KEYWORDS):
            print(f"[GraphPlanner] Routed to RETRIEVE")
            return PlannerResult("retrieve")

        print(f"[GraphPlanner] Routed to LLM")
        return PlannerResult("llm")
