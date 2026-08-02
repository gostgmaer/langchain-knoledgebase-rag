# Middleware request id
from __future__ import annotations

from uuid import uuid4

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

try:
    from opentelemetry import trace as _otel_trace
except ImportError:  # pragma: no cover - opentelemetry is an optional dependency
    _otel_trace = None


def _current_trace_id() -> str | None:
    """
    Returns the active OpenTelemetry span's trace_id as a hex string,
    or None if OTel isn't installed/configured, there's no active
    span, or `trace.get_current_span()` simply can't see one from
    here — confirmed live (and via an isolated, app-independent repro
    with zero custom middleware) that `opentelemetry-instrumentation-
    fastapi` 0.65b0's ASGI-level span isn't visible as "current" from
    inside a route handler in this stack, a known-class Starlette/OTel
    context-propagation gap, not something introduced by this app's
    own code. Kept anyway: harmless when it returns None (trace_id is
    just omitted from the bound fields), and correct automatically if
    a future opentelemetry-instrumentation-fastapi release fixes the
    underlying visibility issue. Never raises.
    """

    if _otel_trace is None:
        return None

    span = _otel_trace.get_current_span()
    context = span.get_span_context()

    if not context.is_valid:
        return None

    return format(context.trace_id, "032x")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Adds a unique request ID to every request, and binds it (plus the
    active OTel trace_id, if any) into structlog's contextvars so
    every log line for the rest of this request carries it — not just
    LoggingMiddleware's own top-level "HTTP Request" line. Previously
    a real, documented gap (docs/BUILD_STATUS.md gap #6): structlog's
    `merge_contextvars` processor was configured but nothing ever
    called `bind_contextvars()`, so the request_id never propagated
    below the one place it was passed explicitly.

    The request ID is available via:

    - request.state.request_id
    - X-Request-ID response header
    - every structlog-emitted log line's "request_id" field
    """

    HEADER_NAME = "X-Request-ID"

    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:

        request_id = request.headers.get(
            self.HEADER_NAME,
            str(uuid4()),
        )

        request.state.request_id = request_id

        trace_id = _current_trace_id()
        bind_kwargs = {"request_id": request_id}
        if trace_id is not None:
            bind_kwargs["trace_id"] = trace_id

        structlog.contextvars.bind_contextvars(**bind_kwargs)

        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()

        response.headers[self.HEADER_NAME] = request_id

        return response