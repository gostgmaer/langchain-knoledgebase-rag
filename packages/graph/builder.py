from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.errors import GraphBubbleUp
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from packages.graph.middleware import (
    LoggingMiddleware,
    MetricsMiddleware,
    MiddlewarePipeline,
)
from packages.graph.nodes import GraphNodes
from packages.graph.otel_middleware import OtelGraphMiddleware
from packages.graph.router import GraphRouter
from packages.graph.state import GraphState

NodeFn = Callable[[GraphState], Awaitable[dict[str, Any] | GraphState]]

# One pipeline shared by every node in every graph build — LoggingMiddleware
# and MetricsMiddleware are both stateless per call (MetricsMiddleware
# writes into the module-level graph_metrics_store, not instance state),
# so a single pipeline instance is safe to reuse across requests despite
# GraphBuilder itself being Factory-scoped (a fresh instance per request,
# per the DI-session-capture lesson learned earlier building memory).
# OtelGraphMiddleware is a no-op whenever OpenTelemetry isn't
# installed/configured (see its own docstring) — safe to always
# include rather than conditionally building the pipeline.
_DEFAULT_PIPELINE = MiddlewarePipeline(LoggingMiddleware(), MetricsMiddleware(), OtelGraphMiddleware())


def _instrumented(name: str, node: NodeFn, pipeline: MiddlewarePipeline = _DEFAULT_PIPELINE) -> NodeFn:
    """
    Wraps a graph node with the middleware pipeline's before/after/
    on_error hooks — LangGraph (Phase 5)'s "Runtime Events" item, now
    genuinely running through packages/graph/middleware.py instead of
    duplicating logging logic here. Wrapping at the `add_node` call
    site (rather than inside each node class) keeps this a single,
    generic instrumentation point instead of touching every node.
    """

    async def wrapper(state: GraphState) -> dict[str, Any] | GraphState:
        await pipeline.before(state, name)
        start = time.monotonic()

        try:
            result = await node(state)
        except GraphBubbleUp:
            # LangGraph's own control-flow signal for interrupt()/Command —
            # not a real error, just an early exit. Skip on_error/after
            # entirely; logging it as "raised" would be misleading noise
            # on every single tool-approval pause.
            raise
        except Exception as exc:
            await pipeline.on_error(state, name, exc)
            raise

        duration_ms = (time.monotonic() - start) * 1000
        await pipeline.after(state, name, duration_ms)
        return result

    return wrapper


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
   supervisor    llm
      │           │
   multi-part?    │
   │        │     │
   ▼        ▼     │
researcher retrieve
   │        │     │
   ▼        └──►──┘
 writer         │
   │       tool calls?
   │        │        │
   │        ▼        ▼
   │      tool       END
   │        │
   │        └──► llm
   │
   └──► END

    Supervisor always runs first whenever the plan needs retrieval,
    deciding whether this turn's question is genuinely multi-part
    (Multi-Agent, docs/mvpRAG.md v2.0) — a decomposition failure or a
    "no" decision falls straight through to `retrieve`, the same
    single-question path that existed before this feature, byte-
    identical. Only a genuinely multi-part question reaches
    `researcher`/`writer`, which never touch `tool` — synthesis over
    already-gathered findings, not a fresh tool-calling turn.

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

        graph.add_node("planner", _instrumented("planner", self._nodes.planner))
        graph.add_node("load_memory", _instrumented("load_memory", self._nodes.load_memory))
        graph.add_node("join", _instrumented("join", _join))
        graph.add_node("retrieve", _instrumented("retrieve", self._nodes.retrieve))
        graph.add_node("tool", _instrumented("tool", self._nodes.tool))
        graph.add_node("llm", _instrumented("llm", self._nodes.llm))
        graph.add_node("supervisor", _instrumented("supervisor", self._nodes.supervisor))
        graph.add_node("researcher", _instrumented("researcher", self._nodes.researcher))
        graph.add_node("writer", _instrumented("writer", self._nodes.writer))

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
                "supervisor": "supervisor",
                "tool": "tool",
                "llm": "llm",
            },
        )

        #
        # Multi-Agent — Supervisor decides whether this turn's question
        # is genuinely multi-part before either path retrieves anything.
        # A "no"/fail-open decision routes to the exact same `retrieve`
        # node the single-question path always used.
        #

        graph.add_conditional_edges(
            "supervisor",
            self._router.route_after_supervisor,
            {
                "researcher": "researcher",
                "retrieve": "retrieve",
            },
        )

        graph.add_edge("researcher", "writer")
        graph.add_edge("writer", END)

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