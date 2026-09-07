# Middleware request id
from __future__ import annotations

from uuid import uuid4

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Adds a unique request ID to every request, and binds it into
    structlog's contextvars so every log line for the rest of this
    request carries it — not just LoggingMiddleware's own top-level
    "HTTP Request" line. Previously a real, documented gap
    (docs/BUILD_STATUS.md gap #6): structlog's `merge_contextvars`
    processor was configured but nothing ever called
    `bind_contextvars()`, so the request_id never propagated below the
    one place it was passed explicitly.

    `trace_id` is deliberately NOT read here via
    `trace.get_current_span()` — confirmed live that
    `opentelemetry-instrumentation-fastapi`'s ASGI-level span isn't
    visible as "current" from inside a `BaseHTTPMiddleware` subclass in
    this stack (a Starlette/OTel context-propagation gap). Instead,
    `packages/shared/tracing.py`'s `_bind_trace_id_hook` binds
    `trace_id` into the same structlog contextvars *before* this
    middleware ever runs, from a point in the ASGI stack where the span
    is genuinely current — so it's already present here for free, this
    middleware just adds `request_id` alongside it.

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

        # trace_id, if any, is already bound by this point — see the
        # class docstring above.
        structlog.contextvars.bind_contextvars(request_id=request_id)

        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()

        response.headers[self.HEADER_NAME] = request_id

        return response