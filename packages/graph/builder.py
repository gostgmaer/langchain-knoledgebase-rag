from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from packages.graph.nodes import GraphNodes
from packages.graph.router import GraphRouter
from packages.graph.state import GraphState


async def _join(state: GraphState) -> GraphState:
    """
    No-op synchronization point for the `planner`/`load_memory` fan-out
    below — LangGraph only runs a node once every one of its incoming
    edges has fired, so this is what guarantees both branches have
    actually finished before `router.route()` reads `execution_plan`.
    """

    return state


class GraphBuilder:
    """
    Production LangGraph builder.

    Flow

           START
          ┌──┴──┐
          ▼     ▼
      planner  load_memory
          └──┬──┘
             ▼
           join
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
         tool       END
           │
           └──► llm

    `planner` and `load_memory` used to run sequentially even though
    neither depends on the other's output — `load_memory` only reads
    the raw last message, never the planner's rewritten query — so
    that ordering was purely an artifact of the order the two
    `add_node` calls happened to be written in, not a real dependency.
    They now fan out from START and run concurrently; `join` (a no-op
    node) is where LangGraph's Pregel-style execution model guarantees
    both branches have actually finished before `router.route()` reads
    `state["execution_plan"]` — a conditional edge can't itself be the
    fan-in point when two *different* nodes lead into it, so a trivial
    join node is the standard way to synchronize parallel branches
    before branching again. This cuts whichever of the two calls is
    faster off the time-to-first-token latency, instead of paying for
    both in sequence on every single turn.

    Memory extraction/summarization no longer runs as a graph node —
    it used to sit between "llm" and END, blocking the HTTP response
    on two more sequential LLM calls for pure side-effect work. It now
    runs as a background task scheduled by the chat router after the
    response is already sent (packages/api/routers/chat.py), reusing
    packages/graph/nodes/extract_memory.py's ExtractMemoryNode directly.
    """

    def __init__(
        self,
        nodes: GraphNodes,
        router: GraphRouter,
        checkpointer: BaseCheckpointSaver,
    ) -> None:
        self._nodes = nodes
        self._router = router
        self._checkpointer = checkpointer

    def build(self) -> CompiledStateGraph:
        graph = StateGraph(GraphState)

        #
        # Nodes
        #

        graph.add_node("planner", self._nodes.planner)
        graph.add_node("load_memory", self._nodes.load_memory)
        graph.add_node("join", _join)
        graph.add_node("retrieve", self._nodes.retrieve)
        graph.add_node("tool", self._nodes.tool)
        graph.add_node("llm", self._nodes.llm)

        #
        # Entry — fan out to planner and load_memory concurrently,
        # since neither depends on the other's output.
        #

        graph.add_edge(START, "planner")
        graph.add_edge(START, "load_memory")

        #
        # Fan back in before routing — router.route() needs both
        # branches' results (state["execution_plan"] from planner).
        #

        graph.add_edge("planner", "join")
        graph.add_edge("load_memory", "join")

        graph.add_conditional_edges(
            "join",
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