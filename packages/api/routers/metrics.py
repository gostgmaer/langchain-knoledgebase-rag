# Router metrics
from __future__ import annotations

from fastapi import APIRouter
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from packages.api.middleware.metrics import metrics_store
from packages.api.responses import ApiResponse
from packages.graph.middleware import graph_metrics_store

router = APIRouter(
    prefix="/metrics",
    tags=["Metrics"],
)


@router.get("")
async def get_metrics():
    """
    Human-readable JSON summary: HTTP request counts/status/duration by
    route (packages/api/middleware/metrics.py), plus graph *node*
    call/duration/error counts by node name (packages/graph/middleware.py) —
    e.g. how many times "retrieve" ran, its average latency, and how
    often it errored, distinct from the HTTP-level view above. Both
    in-memory, per-process, reset on restart. For a real Prometheus
    server to scrape, use GET /metrics/prometheus instead — this JSON
    shape isn't the Prometheus exposition format.
    """

    return ApiResponse(
        message="Metrics retrieved.",
        data={
            "http": metrics_store.snapshot(),
            "graph_nodes": graph_metrics_store.snapshot(),
        },
    )


@router.get("/prometheus")
async def get_prometheus_metrics():
    """
    Real Prometheus text-exposition-format metrics (docs/BUGS.md item 10),
    for a real Prometheus server's scrape config to point at — the plain
    `GET /metrics` above is a JSON convenience view, not this format.
    Per-process, like the JSON view: a standard multi-replica deployment
    scrapes every replica's own endpoint and aggregates across them at
    query time, which is the correct pattern, not something this endpoint
    itself needs to do.
    """

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
