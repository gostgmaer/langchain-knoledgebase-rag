from langgraph.graph import END, START, StateGraph

from .nodes import chat_node
from .router import router
from .state import GraphState


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("chat", chat_node)

    graph.add_edge(START, "chat")

    graph.add_conditional_edges(
        "chat",
        router,
        {
            END: END,
        },
    )

    return graph.compile()