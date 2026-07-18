# Graph builder
from __future__ import annotations


from langgraph.graph import (
    END,
    START,
    StateGraph,
)

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

        # Nodes

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

        graph.add_node(
            "summarize",
            self.nodes.summarize,
        )

        #
        # START
        #

        graph.add_conditional_edges(
            START,
            self.router.route,
        )

        #
        # retrieve
        #

        graph.add_edge(
            "retrieve",
            "llm",
        )

        #
        # tool
        #

        graph.add_edge(
            "tool",
            "llm",
        )

        #
        # llm
        #

        graph.add_conditional_edges(
            "llm",
            self.router.should_summarize,
        )

        #
        # summarize
        #

        graph.add_edge(
            "summarize",
            END,
        )

        return graph.compile()