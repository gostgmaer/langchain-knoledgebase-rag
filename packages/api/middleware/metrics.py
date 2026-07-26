from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class MetricsStore:
    """
    Process-local request metrics — Production hardening's own
    "Metrics middleware" gap. `opentelemetry-*` is a declared
    dependency but was never wired anywhere in this app, and there's no
    reachable OTLP collector in this environment to export to (same
    "unprovable without real infra" situation as Docker/Deployment) —
    this is a genuinely self-contained, live-verifiable alternative:
    counters/timers kept in memory, read back through
    `GET /api/v1/metrics`.

    In-memory only, same scoping caveat as the rate limiter: per
    process, resets on restart, doesn't aggregate across replicas.
    """

    def __init__(self) -> None:
        self.request_count: dict[str, int] = defaultdict(int)
        self.status_count: dict[int, int] = defaultdict(int)
        self.total_duration_seconds: dict[str, float] = defaultdict(float)

    def record(self, route: str, status_code: int, duration_seconds: float) -> None:
        self.request_count[route] += 1
        self.status_count[status_code] += 1
        self.total_duration_seconds[route] += duration_seconds

    def snapshot(self) -> dict:
        return {
            "requests_by_route": dict(self.request_count),
            "responses_by_status": {
                str(code): count for code, count in self.status_count.items()
            },
            "avg_duration_ms_by_route": {
                route: round((self.total_duration_seconds[route] / count) * 1000, 2)
                for route, count in self.request_count.items()
            },
        }


metrics_store = MetricsStore()


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start

        route = request.scope.get("route")
        path_template = route.path if route is not None else request.url.path

        metrics_store.record(path_template, response.status_code, duration)

        return response
