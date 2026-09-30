from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# Real Prometheus metrics (docs/BUGS.md item 10: GET /api/v1/metrics used to be a JSON dump of the
# MetricsStore below, not the Prometheus text exposition format, so no real Prometheus server could
# scrape it at all). Per-process, same as MetricsStore — that's correct, not a gap: a standard
# Prometheus deployment scrapes every replica's own /metrics endpoint separately and aggregates
# across replicas at query time (`sum(...) by (...)`), it doesn't expect one instance's endpoint to
# already report a cluster-wide total.
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests handled",
    ("route", "status"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ("route",),
)


class MetricsStore:
    """
    Process-local request metrics, backing the human-readable
    `GET /api/v1/metrics` JSON summary — kept alongside the real
    Prometheus counters above (`GET /api/v1/metrics/prometheus`) since
    it's a genuinely different, simpler consumer (a quick glance, no
    Prometheus server required), not a duplicate of the same data.

    In-memory only, same scoping caveat as the rate limiter: per
    process, resets on restart, doesn't aggregate across replicas — see
    the Prometheus counters' own docstring above for why that's the
    expected shape for the real (Prometheus-scraped) metrics, not this
    JSON convenience view.
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
        HTTP_REQUESTS_TOTAL.labels(route=path_template, status=str(response.status_code)).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(route=path_template).observe(duration)

        return response
