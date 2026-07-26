from __future__ import annotations

import httpx

from packages.infrastructure.http.retry import RetryTransport


def create_http_client() -> httpx.AsyncClient:
    """Create shared HTTP client, with retry-on-transient-failure built in."""

    return httpx.AsyncClient(
        transport=RetryTransport(httpx.AsyncHTTPTransport()),
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