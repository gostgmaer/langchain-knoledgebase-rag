# Middleware logging
from __future__ import annotations

import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from packages.shared.logging import get_logger

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs every HTTP request and response.

    Logged information:
        - Method
        - Path
        - Status Code
        - Duration
        - Request ID
        - Client IP
    """

    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:

        start = time.perf_counter()

        response = None

        try:
            response = await call_next(request)
            return response

        finally:

            duration_ms = round(
                (time.perf_counter() - start) * 1000,
                2,
            )

            logger.info(
                "HTTP Request",
                method=request.method,
                path=request.url.path,
                query=str(request.url.query),
                status_code=response.status_code if response else 500,
                duration_ms=duration_ms,
                request_id=getattr(
                    request.state,
                    "request_id",
                    None,
                ),
                client_ip=request.client.host if request.client else None,
                user_agent=request.headers.get("User-Agent"),
            )