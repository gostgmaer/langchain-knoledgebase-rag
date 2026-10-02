# Middleware security headers
from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from packages.config.loader import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds baseline security response headers (docs/BUILD_STATUS.md gap #2:
    "No CSP/X-Frame-Options or other security headers exist yet").

    Content-Security-Policy is skipped on the interactive API docs
    (/docs, /redoc) since Swagger UI/ReDoc load their JS/CSS from a CDN
    under a `default-src 'self'` policy — those routes are already gated
    off entirely in production (packages/api/app.py), so this only ever
    matters in development. Every other header applies to every
    response, including the docs, since none of them affect a CDN
    script/style load.
    """

    _DOC_PATHS = frozenset(
        {
            settings.api.docs_url,
            settings.api.redoc_url,
        }
    )

    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:

        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        if request.url.path not in self._DOC_PATHS:
            response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"

        return response
