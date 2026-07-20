from __future__ import annotations

from packages.graph.nodes.planner import NextNode
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

        print(f"[Router] Next node: {plan.next_node}")

        match plan.next_node:

            case NextNode.RETRIEVE:
                return "retrieve"

            case NextNode.TOOL:
                return "tool"

            case NextNode.LLM:
                return "llm"

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