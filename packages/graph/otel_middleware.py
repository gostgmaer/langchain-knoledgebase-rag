from __future__ import annotations

from packages.graph.middleware import GraphMiddleware
from packages.graph.state import GraphState
from packages.shared.logging import get_logger

logger = get_logger(__name__)


class OtelGraphMiddleware(GraphMiddleware):
    """
    Wraps every graph node execution in its own OpenTelemetry span,
    nested under the request's active span (FastAPI's auto-instrumented
    HTTP span — see packages/shared/tracing.py) — so one trace shows
    the full HTTP request AND every individual node it ran through,
    not just an opaque "graph ran" black box.

    `before()`/`after()`/`on_error()` are separate calls with no
    shared call-context object between them (see GraphMiddleware's own
    interface), so the open span + its context-attach token are
    stashed in a dict keyed by `(id(state), node_name)` — safe because
    a given node only has one in-flight execution per state object at
    a time, even though multiple *different* state objects (LangGraph's
    parallel fan-out, e.g. planner/load_memory) can be in flight
    concurrently.

    A no-op if OpenTelemetry isn't installed/configured — matches
    every other optional-infra integration in this app.
    """

    def __init__(self) -> None:
        self._open: dict[tuple[int, str], tuple[object, object]] = {}

        try:
            from opentelemetry import trace

            self._tracer = trace.get_tracer("packages.graph")
        except ImportError:
            self._tracer = None

    async def before(self, state: GraphState, node_name: str) -> None:
        if self._tracer is None:
            return

        from opentelemetry import context as otel_context
        from opentelemetry import trace

        span = self._tracer.start_span(f"graph.node.{node_name}")
        span.set_attribute("graph.node", node_name)

        conversation_id = state.get("conversation_id")
        if conversation_id is not None:
            span.set_attribute("graph.conversation_id", str(conversation_id))

        token = otel_context.attach(trace.set_span_in_context(span))
        self._open[(id(state), node_name)] = (span, token)

    async def after(self, state: GraphState, node_name: str, duration_ms: float) -> None:
        self._end_span(state, node_name, exc=None)

    async def on_error(self, state: GraphState, node_name: str, exc: Exception) -> None:
        self._end_span(state, node_name, exc=exc)

    def _end_span(self, state: GraphState, node_name: str, exc: Exception | None) -> None:
        entry = self._open.pop((id(state), node_name), None)
        if entry is None:
            return

        span, token = entry

        try:
            from opentelemetry import context as otel_context
            from opentelemetry.trace import Status, StatusCode

            if exc is not None:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
            else:
                span.set_status(Status(StatusCode.OK))

            span.end()
            otel_context.detach(token)
        except Exception:
            logger.exception("Failed to close OTel span for graph node", node=node_name)
