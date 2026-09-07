from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from packages.config.observability import ObservabilitySettings
from packages.shared.logging import get_logger

logger = get_logger(__name__)


def _bind_trace_id_hook(span: Any, scope: dict) -> None:
    """
    `FastAPIInstrumentor`'s `server_request_hook` — called synchronously
    from inside `OpenTelemetryMiddleware.__call__`'s own
    `with trace.use_span(span, ...)` block, *before* `await self.app(...)`
    ever hands control to Starlette's middleware stack (verified against
    this project's installed `opentelemetry-instrumentation-asgi`
    source). That timing is exactly why this exists instead of calling
    `trace.get_current_span()` later, e.g. from
    `packages/api/middleware/request_id.py`: this project confirmed live
    (and via an isolated, app-independent repro) that
    `opentelemetry-instrumentation-fastapi` 0.65b0's ASGI-level span
    stops being visible as "current" once Starlette's `BaseHTTPMiddleware`
    (every middleware in `packages/api/middleware/`) re-enters via its
    own task boundary. A plain `structlog.contextvars.ContextVar`
    binding, set here in the same task *before* that boundary is ever
    crossed, propagates forward into every descendant task the normal
    Python way — sidestepping OTel's own context-propagation gap
    entirely rather than working around it after the fact.

    Never raises: `FastAPIInstrumentor` already wraps every hook in a
    failsafe that logs+swallows, but binding a context var can't
    realistically fail anyway.
    """

    if span is None or not span.get_span_context().is_valid:
        return

    import structlog

    trace_id = format(span.get_span_context().trace_id, "032x")
    structlog.contextvars.bind_contextvars(trace_id=trace_id)


def configure_opentelemetry(app: FastAPI, settings: ObservabilitySettings) -> bool:
    """
    Sets up a real OTel `TracerProvider` + OTLP exporter and
    instruments FastAPI + httpx, so one trace spans the full request:
    HTTP -> every LangGraph node (see packages/graph/otel_middleware.py)
    -> outbound calls (IAM, Upload Service, LLM provider SDKs that
    route through httpx).

    Non-fatal: if the collector is unreachable or setup fails for any
    other reason, this logs a warning and returns False instead of
    blocking startup — matching every other optional-infra integration
    in this app (the Postgres checkpointer, the arq queue pool).
    """

    if not settings.otel_enabled:
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({"service.name": settings.otel_service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app, server_request_hook=_bind_trace_id_hook)
        HTTPXClientInstrumentor().instrument()

        return True

    except Exception as exc:
        logger.warning("Could not set up OpenTelemetry, tracing disabled: %s", exc)
        return False
