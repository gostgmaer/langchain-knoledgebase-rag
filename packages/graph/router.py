from __future__ import annotations

from langgraph.graph import END

from packages.graph.nodes.planner import NextNode
from packages.graph.state import GraphState


class GraphRouter:

    def route(
        self,
        state: GraphState,
    ) -> str:

        plan = state["execution_plan"]

        print(f"[GraphRouter] Routing to: {plan.next_node}")

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
            print(f"[GraphRouter] Tool calls detected, routing to TOOL")
            return "tool"

        print(f"[GraphRouter] Final LLM response generated, routing to END")
        return END