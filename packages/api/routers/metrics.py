# Router metrics
from __future__ import annotations

from fastapi import APIRouter

from packages.api.middleware.metrics import metrics_store
from packages.api.responses import ApiResponse

router = APIRouter(
    prefix="/metrics",
    tags=["Metrics"],
)


@router.get("")
async def get_metrics():
    """
    Process-local request metrics collected by MetricsMiddleware —
    request counts, response status counts, and average duration, all
    grouped by route. See packages/api/middleware/metrics.py for scope
    and limitations (in-memory, per-process, resets on restart).
    """

    return ApiResponse(
        message="Metrics retrieved.",
        data=metrics_store.snapshot(),
    )
