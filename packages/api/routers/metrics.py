# Router metrics
from __future__ import annotations

from fastapi import APIRouter

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
    Process-local metrics: HTTP request counts/status/duration by
    route (packages/api/middleware/metrics.py), plus graph *node*
    call/duration/error counts by node name (packages/graph/middleware.py) —
    e.g. how many times "retrieve" ran, its average latency, and how
    often it errored, distinct from the HTTP-level view above. Both
    in-memory, per-process, reset on restart.
    """

    return ApiResponse(
        message="Metrics retrieved.",
        data={
            "http": metrics_store.snapshot(),
            "graph_nodes": graph_metrics_store.snapshot(),
        },
    )
