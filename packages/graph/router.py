from __future__ import annotations

from langgraph.graph import END

from packages.graph.state import GraphState


class GraphRouter:

    def route(
        self,
        state: GraphState,
    ) -> str:
        print(f"[GraphRouter] Routing from planner to: {state['next_node']}")
        return state["next_node"]

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