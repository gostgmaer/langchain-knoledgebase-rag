from __future__ import annotations

import httpx


def create_http_client() -> httpx.AsyncClient:
    """Create shared HTTP client."""

    return httpx.AsyncClient(
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