from __future__ import annotations

from langgraph.graph import END

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

        # Memory extraction/summarization used to run here as a graph
        # node, blocking the HTTP response on two more sequential LLM
        # calls that have zero effect on the reply the user is waiting
        # for. It now runs as a background task scheduled by the chat
        # router after the response is sent (packages/api/routers/chat.py),
        # the same "never block the request path" pattern already used
        # for document ingestion.
        return END