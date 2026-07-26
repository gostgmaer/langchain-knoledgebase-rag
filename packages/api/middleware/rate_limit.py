from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from packages.config.loader import settings

WINDOW_SECONDS = 60.0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-tenant (falls back to client IP) sliding-window rate limit —
    Production hardening's own pending gap.

    Keyed by the raw X-Tenant-ID header rather than TenantMiddleware's
    resolved request.state.tenant_id, so this middleware has no
    ordering dependency on Tenant/Auth and can sit as close to the edge
    (right after CORS) as possible — rejecting abusive traffic before
    it costs a tenant resolution, a log line, or an IAM round-trip.

    In-memory only: resets on restart, doesn't share state across
    multiple API server processes — the same known limitation already
    documented for packages/knowledge/embeddings/rate_limiter.py. Fine
    for a single-process deployment; a horizontally-scaled one would
    need a Redis-backed counter instead.
    """

    def __init__(self, app) -> None:
        super().__init__(app)
        self._max_requests = settings.api.rate_limit_requests_per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next) -> Response:
        if self._max_requests <= 0:
            return await call_next(request)

        key = request.headers.get("X-Tenant-ID") or (
            request.client.host if request.client else "unknown"
        )

        now = time.monotonic()
        hits = self._hits[key]
        cutoff = now - WINDOW_SECONDS
        while hits and hits[0] < cutoff:
            hits.popleft()

        if len(hits) >= self._max_requests:
            retry_after = int(WINDOW_SECONDS - (now - hits[0])) + 1
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "message": "Rate limit exceeded. Try again shortly.",
                },
                headers={"Retry-After": str(retry_after)},
            )

        hits.append(now)
        return await call_next(request)
