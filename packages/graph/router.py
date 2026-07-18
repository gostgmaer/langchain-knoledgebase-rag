from __future__ import annotations

from langgraph.graph import END

from packages.graph.state import GraphState


class GraphRouter:

    def route(
        self,
        state: GraphState,
    ) -> str:

        message = state["messages"][-1]

        if getattr(message, "tool_calls", None):
            return "tool"

        if state.get("documents") is None:
            return "retrieve"

        return "llm"

    def should_summarize(
        self,
        state: GraphState,
    ) -> str:

        if len(state["messages"]) > 30:
            return "summarize"

        return END