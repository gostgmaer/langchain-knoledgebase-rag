from __future__ import annotations

import httpx

from packages.config.loader import settings
from packages.infrastructure.http.retry import RetryTransport


def create_http_client() -> httpx.AsyncClient:
    """Create shared HTTP client, with retry-on-transient-failure and
    per-host circuit breaking built in."""

    return httpx.AsyncClient(
        transport=RetryTransport(
            httpx.AsyncHTTPTransport(),
            breaker_failure_threshold=settings.queue.circuit_breaker_failure_threshold,
            breaker_reset_timeout_seconds=settings.queue.circuit_breaker_reset_seconds,
        ),
        timeout=httpx.Timeout(
            timeout=30.0,
            connect=10.0,
        ),
        limits=httpx.Limits(
            max_connections=100,
            max_keepalive_connections=20,
        ),
        follow_redirects=True,
    )