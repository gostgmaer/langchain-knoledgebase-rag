from __future__ import annotations

from langgraph.graph import END

from packages.graph.state import GraphState


class GraphRouter:

    def route(
        self,
        state: GraphState,
    ) -> str:
        return state["next_node"]

    def after_llm(
        self,
        state: GraphState,
    ) -> str:

        message = state["messages"][-1]

        if getattr(message, "tool_calls", None):
            return "tool"

        return END