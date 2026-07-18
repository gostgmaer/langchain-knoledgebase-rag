from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from packages.graph.nodes import GraphNodes
from packages.graph.router import GraphRouter
from packages.graph.state import GraphState


class GraphBuilder:

    def __init__(
        self,
        nodes: GraphNodes,
        router: GraphRouter,
    ) -> None:
        self.nodes = nodes
        self.router = router
        

    def build(self):

        graph = StateGraph(GraphState)

        #
        # Nodes
        #

        graph.add_node(
            "planner",
            self.nodes.planner,
        )

        graph.add_node(
            "retrieve",
            self.nodes.retrieve,
        )

        graph.add_node(
            "tool",
            self.nodes.tool,
        )

        graph.add_node(
            "llm",
            self.nodes.llm,
        )

        #
        # Start
        #

        graph.add_edge(
            START,
            "planner",
        )

        #
        # Planner
        #

        graph.add_conditional_edges(
            "planner",
            self.router.route,
            {
                "retrieve": "retrieve",
                "tool": "tool",
                "llm": "llm",
            },
        )

        #
        # Retrieval
        #

        graph.add_edge(
            "retrieve",
            "llm",
        )

        #
        # Tool
        #

        graph.add_edge(
            "tool",
            "llm",
        )

        #
        # LLM
        #

        graph.add_conditional_edges(
            "llm",
            self.router.after_llm,
            {
                "tool": "tool",
                END: END,
            },
        )
        
        return graph.compile()