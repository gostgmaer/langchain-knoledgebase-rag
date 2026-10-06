from __future__ import annotations

import time

from fastapi import Request
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from packages.config.loader import settings
from packages.shared.logging import get_logger

logger = get_logger(__name__)

WINDOW_SECONDS = 60

# Module-level, like packages/tools/builtin/weather.py's httpx client: constructed once, shared by
# every RateLimitMiddleware instance (there's only ever one, but this also means a fresh instance
# reuses the same connection pool rather than opening a new one). close_rate_limit_redis() is
# called from lifespan's shutdown, same idiom as close_weather_client().
_redis = Redis.from_url(str(settings.redis.url), encoding="utf-8", decode_responses=True)


async def close_rate_limit_redis() -> None:
    """Closes the module-level Redis client — call from lifespan's shutdown."""

    await _redis.aclose()


async def is_rate_limited(name: str, key: str, max_requests: int, *, window_seconds: int = WINDOW_SECONDS) -> bool:
    """
    The same fixed-window Redis counter RateLimitMiddleware uses, as a standalone check for a
    route that needs its own, narrower limit (packages/api/routers/widget.py: a public,
    unauthenticated endpoint needs a much tighter cap than the general per-tenant one). Fails
    open on a Redis error, same reasoning as the middleware.
    """

    if max_requests <= 0:
        return False
    bucket = int(time.time() // window_seconds)
    redis_key = f"ratelimit:{name}:{key}:{bucket}"
    try:
        async with _redis.pipeline(transaction=True) as pipe:
            pipe.incr(redis_key)
            pipe.expire(redis_key, window_seconds + 1)
            count, _ = await pipe.execute()
    except Exception:
        logger.warning("Rate limiter: Redis unreachable, failing open for this request")
        return False
    return count > max_requests


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-tenant (falls back to client IP) rate limit, backed by Redis so the
    limit is actually shared across every API replica — docs/BUGS.md item 2:
    the previous in-memory `dict` reset per-process and silently multiplied
    the effective limit under >1 replica.

    Fixed-window (not sliding-window like the in-memory version it
    replaces): each tenant/IP gets one Redis counter keyed by
    `<tenant-or-ip>:<60s bucket>`, incremented atomically and given a TTL so
    it self-expires. This trades exact precision for something that's
    genuinely correct under concurrent, multi-replica access without a Lua
    script — a burst is possible right at a window boundary (up to ~2x the
    limit across two adjacent windows), which is an accepted, standard
    trade-off for abuse protection, not a billing-grade guarantee.

    Fails open on a Redis error (same "degrade, don't crash" idiom already
    used for the checkpointer and the job queue elsewhere in this app) —
    losing the rate limit temporarily is preferable to a Redis blip taking
    the whole API down.
    """

    # Routes that trigger a real LLM call or a file write get the tighter
    # `rate_limit_expensive_requests_per_minute` cap, layered on top of the
    # general one — docs/BUGS.md item 12. `(method, path_prefix)`; method
    # `None` matches any method. Document upload is POST-only (GET
    # /documents is a cheap list/read, not worth the tighter cap).
    EXPENSIVE_ROUTES: tuple[tuple[str | None, str], ...] = (
        (None, "/chat"),
        (None, "/search"),
        ("POST", "/documents"),
    )

    def __init__(self, app) -> None:
        super().__init__(app)
        self._max_requests = settings.api.rate_limit_requests_per_minute
        self._max_expensive_requests = settings.api.rate_limit_expensive_requests_per_minute

    def _is_expensive(self, request: Request) -> bool:
        path = request.url.path.removeprefix(settings.api.api_prefix)
        return any(
            (method is None or method == request.method) and path.startswith(prefix)
            for method, prefix in self.EXPENSIVE_ROUTES
        )

    async def _check(self, name: str, key: str, max_requests: int) -> Response | None:
        """Returns a 429 Response if this bucket is over its limit, else None."""

        if await is_rate_limited(name, key, max_requests):
            retry_after = WINDOW_SECONDS - (int(time.time()) % WINDOW_SECONDS) + 1
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "message": "Rate limit exceeded. Try again shortly.",
                },
                headers={"Retry-After": str(retry_after)},
            )
        return None

    async def dispatch(self, request: Request, call_next) -> Response:
        if self._max_requests <= 0 and self._max_expensive_requests <= 0:
            return await call_next(request)

        key = request.headers.get("X-Tenant-ID") or (
            request.client.host if request.client else "unknown"
        )

        rejection = await self._check("general", key, self._max_requests)
        if rejection is not None:
            return rejection

        if self._is_expensive(request):
            rejection = await self._check("expensive", key, self._max_expensive_requests)
            if rejection is not None:
                return rejection

        return await call_next(request)
