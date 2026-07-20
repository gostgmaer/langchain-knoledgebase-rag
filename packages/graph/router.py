from __future__ import annotations

from packages.planner.models import Capability
from packages.graph.state import GraphState


class GraphRouter:
    """
    Handles all routing decisions inside the graph.
    """

    def route(
        self,
        state: GraphState,
    ) -> str:

        plan = state["execution_plan"]

        if plan.has(Capability.RETRIEVAL):
            print("[Router] Next node: retrieve")
            return "retrieve"

        print("[Router] Next node: llm")
        return "llm"

    def after_llm(
        self,
        state: GraphState,
    ) -> str:

        message = state["messages"][-1]

        if getattr(message, "tool_calls", None):
            print("[Router] Tool calls detected")
            return "tool"

        print("[Router] Conversation finished")

        return "extract_memory"