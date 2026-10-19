from __future__ import annotations

from langgraph.graph import END

from packages.graph.state import GraphState
from packages.planner.models import Capability
from packages.shared.logging import get_logger

logger = get_logger(__name__)


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
            # Multi-part classification (Multi-Agent, docs/mvpRAG.md
            # v2.0) is decided by `planner` itself, in the same START
            # fan-out as load_memory, not as a separate routing hop
            # (packages/graph/builder.py, docs/BUGS.md item 63) — by
            # the time this runs, state["is_multi_part"] is already
            # set. A genuinely multi-part question goes to
            # researcher/writer; a decomposition failure or a "no"
            # decision falls through to the single-question path,
            # byte-identical to this graph's behavior before
            # Multi-Agent existed.
            if state.get("is_multi_part"):
                logger.debug("Routing decision", next_node="researcher")
                return "researcher"

            logger.debug("Routing decision", next_node="retrieve")
            return "retrieve"

        logger.debug("Routing decision", next_node="llm")
        return "llm"

    def after_llm(
        self,
        state: GraphState,
    ) -> str:

        message = state["messages"][-1]

        if getattr(message, "tool_calls", None):
            logger.debug("Routing decision", next_node="tool", tool_calls=True)
            return "tool"

        logger.debug("Routing decision", next_node="END")

        # Memory extraction/summarization used to run here as a graph
        # node, blocking the HTTP response on two more sequential LLM
        # calls that have zero effect on the reply the user is waiting
        # for. It now runs as a background task scheduled by the chat
        # router after the response is sent (packages/api/routers/chat.py),
        # the same "never block the request path" pattern already used
        # for document ingestion.
        return END