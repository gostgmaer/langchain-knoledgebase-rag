from __future__ import annotations

from fastapi import FastAPI

from packages.config.observability import ObservabilitySettings
from packages.shared.logging import get_logger

logger = get_logger(__name__)


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

        FastAPIInstrumentor.instrument_app(app)
        HTTPXClientInstrumentor().instrument()

        return True

    except Exception as exc:
        logger.warning("Could not set up OpenTelemetry, tracing disabled: %s", exc)
        return False
