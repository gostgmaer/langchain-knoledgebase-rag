# Graph builder
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from packages.chat.chat_service import ChatService
from packages.graph.nodes.agent import AgentNode
from packages.graph.state import AgentState
from langgraph.checkpoint.memory import MemorySaver

class GraphBuilder:
    """
    Responsible for constructing the LangGraph workflow.

    This class wires nodes together but contains no business logic.
    """

    def __init__(
        self,
        chat_service: ChatService,
    ) -> None:
        self._chat_service = chat_service
        self._checkpointer = MemorySaver()

    def build(self):
        graph = StateGraph(AgentState)

        #
        # Nodes
        #
        graph.add_node(
            "agent",
            AgentNode(self._chat_service),
        )

        #
        # Edges
        #
        graph.add_edge(START, "agent")
        graph.add_edge("agent", END)

        return graph.compile(
            checkpointer=self._checkpointer,
        )