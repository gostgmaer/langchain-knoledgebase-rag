from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from packages.graph.nodes import GraphNodes
from packages.graph.router import GraphRouter
from packages.graph.state import GraphState
from packages.planner.models import Capability, ExecutionPlan, ExecutionStep

# The checkpointer serializes graph state (including these custom planner
# types) with msgpack. Unregistered types are currently allowed with just a
# warning, but LangGraph's own message says this will be blocked in a future
# version (or immediately, if LANGGRAPH_STRICT_MSGPACK=true is ever set) —
# so these need to be explicitly allowlisted rather than relying on the
# permissive default forever.
_CHECKPOINT_SERDE = JsonPlusSerializer().with_msgpack_allowlist(
    [
        Capability,
        ExecutionStep,
        ExecutionPlan,
        ("asyncpg.pgproto.pgproto", "UUID"),
    ]
)


class GraphBuilder:
    """
    Production LangGraph builder.

    Flow

        START
          │
          ▼
      planner
          │
          ▼
     load_memory
          │
          ▼
        router
      ┌───────────┐
      │           │
      ▼           ▼
   retrieve      llm
      │           │
      └─────►─────┘
                │
          tool calls?
           │        │
           ▼        ▼
         tool   extract_memory
           │        │
           └──► llm │
                    ▼
                   END
    """

    def __init__(
        self,
        nodes: GraphNodes,
        router: GraphRouter,
    ) -> None:
        self._nodes = nodes
        self._router = router
        self._checkpointer = MemorySaver(serde=_CHECKPOINT_SERDE)

    def build(self) -> CompiledStateGraph:
        graph = StateGraph(GraphState)

        #
        # Nodes
        #

        graph.add_node("planner", self._nodes.planner)
        graph.add_node("load_memory", self._nodes.load_memory)
        graph.add_node("retrieve", self._nodes.retrieve)
        graph.add_node("tool", self._nodes.tool)
        graph.add_node("llm", self._nodes.llm)
        graph.add_node("extract_memory", self._nodes.extract_memory)

        #
        # Entry
        #

        graph.add_edge(START, "planner")

        #
        # Planner
        #

        graph.add_edge("planner", "load_memory")

        #
        # Memory -> Router
        #

        graph.add_conditional_edges(
            "load_memory",
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
                "extract_memory": "extract_memory",
            },
        )

        #
        # Finish
        #

        graph.add_edge("extract_memory", END)

        return graph.compile(
            checkpointer=self._checkpointer,
        )