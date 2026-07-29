# Graph middleware
from __future__ import annotations

from collections import defaultdict
from typing import Any

from packages.graph.state import GraphState
from packages.shared.logging import get_logger

logger = get_logger(__name__)


class GraphMiddleware:
    """
    Base middleware — before/after/on_error hooks around every graph
    node's execution. Wired in for real via `GraphBuilder`'s
    `instrumented()` wrapper (see below), not per-node boilerplate.
    """

    async def before(self, state: GraphState, node_name: str) -> None:
        pass

    async def after(self, state: GraphState, node_name: str, duration_ms: float) -> None:
        pass

    async def on_error(self, state: GraphState, node_name: str, exc: Exception) -> None:
        pass


class LoggingMiddleware(GraphMiddleware):
    """
    Structured entered/exited/raised events per node — LangGraph
    (Phase 5)'s "Runtime Events" item.
    """

    async def before(self, state: GraphState, node_name: str) -> None:
        logger.info(
            "Graph node entered",
            node=node_name,
            conversation_id=str(state.get("conversation_id")),
        )

    async def after(self, state: GraphState, node_name: str, duration_ms: float) -> None:
        logger.info(
            "Graph node exited",
            node=node_name,
            conversation_id=str(state.get("conversation_id")),
            duration_ms=round(duration_ms, 2),
        )

    async def on_error(self, state: GraphState, node_name: str, exc: Exception) -> None:
        logger.error(
            "Graph node raised",
            node=node_name,
            conversation_id=str(state.get("conversation_id")),
            error=str(exc),
            error_type=type(exc).__name__,
        )


class GraphMetricsStore:
    """
    Process-local, per-node call/duration/error counters — genuinely
    new, not a duplicate of packages/api/middleware/metrics.py's HTTP
    request metrics: that one counts requests by route; this counts
    graph *node* executions (e.g. "retrieve ran 47 times, 2.1s avg,
    2 errors"), which no other part of this app currently exposes.
    Same in-memory, per-process, resets-on-restart scoping as the HTTP
    metrics store — a horizontally-scaled deployment would need a
    shared backend instead.
    """

    def __init__(self) -> None:
        self.calls: dict[str, int] = defaultdict(int)
        self.total_duration_ms: dict[str, float] = defaultdict(float)
        self.errors: dict[str, int] = defaultdict(int)

    def record(self, node_name: str, duration_ms: float, *, error: bool) -> None:
        self.calls[node_name] += 1
        if error:
            self.errors[node_name] += 1
        else:
            self.total_duration_ms[node_name] += duration_ms

    def snapshot(self) -> dict[str, Any]:
        return {
            node: {
                "calls": count,
                "errors": self.errors.get(node, 0),
                "avg_duration_ms": (
                    round(self.total_duration_ms[node] / (count - self.errors.get(node, 0)), 2)
                    if count - self.errors.get(node, 0) > 0
                    else 0
                ),
            }
            for node, count in self.calls.items()
        }


graph_metrics_store = GraphMetricsStore()


class MetricsMiddleware(GraphMiddleware):
    """Records every node call into the shared `graph_metrics_store`."""

    async def after(self, state: GraphState, node_name: str, duration_ms: float) -> None:
        graph_metrics_store.record(node_name, duration_ms, error=False)

    async def on_error(self, state: GraphState, node_name: str, exc: Exception) -> None:
        graph_metrics_store.record(node_name, 0.0, error=True)


class MiddlewarePipeline:
    """
    Runs a set of middlewares around a node: `before` in registration
    order, `after`/`on_error` in reverse (the same in/out nesting
    convention as HTTP middleware — the first-registered middleware is
    the outermost).
    """

    def __init__(self, *middlewares: GraphMiddleware) -> None:
        self.middlewares = middlewares

    async def before(self, state: GraphState, node_name: str) -> None:
        for middleware in self.middlewares:
            await middleware.before(state, node_name)

    async def after(self, state: GraphState, node_name: str, duration_ms: float) -> None:
        for middleware in reversed(self.middlewares):
            await middleware.after(state, node_name, duration_ms)

    async def on_error(self, state: GraphState, node_name: str, exc: Exception) -> None:
        for middleware in reversed(self.middlewares):
            await middleware.on_error(state, node_name, exc)
