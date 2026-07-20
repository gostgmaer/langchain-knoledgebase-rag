from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from packages.graph.nodes import GraphNodes
from packages.graph.router import GraphRouter
from packages.graph.state import GraphState


class GraphBuilder:

    def __init__(
        self,
        nodes: GraphNodes,
        router: GraphRouter,
    ) -> None:
        self._nodes = nodes
        self._router = router
        self._checkpointer = MemorySaver()

    def build(self) -> CompiledStateGraph:

        graph = StateGraph(GraphState)

        #
        # Nodes
        #

        graph.add_node("planner", self._nodes.planner)
        graph.add_node("retrieve", self._nodes.retrieve)
        graph.add_node("tool", self._nodes.tool)
        graph.add_node("llm", self._nodes.llm)

        #
        # Start
        #

        graph.add_edge(START, "planner")

        #
        # Planner
        #

        graph.add_conditional_edges(
            "planner",
            self._router.route,
            {
                "retrieve": "retrieve",
                "tool": "tool",
                "llm": "llm",
            },
        )

        #
        # Retrieval
        #

        graph.add_edge("retrieve", "llm")

        #
        # Tool
        #

        graph.add_edge("tool", "llm")

        #
        # LLM
        #

        graph.add_conditional_edges(
            "llm",
            self._router.after_llm,
            {
                "tool": "tool",
                END: END,
            },
        )

        return graph.compile(
            checkpointer=self._checkpointer,
        )
