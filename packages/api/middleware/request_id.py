# Middleware request id
from __future__ import annotations

from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Adds a unique request ID to every request.

    The request ID is available via:

    - request.state.request_id
    - X-Request-ID response header
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

        response = await call_next(request)

        response.headers[self.HEADER_NAME] = request_id

        return response