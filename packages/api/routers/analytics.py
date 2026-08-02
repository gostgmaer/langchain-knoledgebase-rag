# Router analytics
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    get_scoped_container,
    require_uuid_header,
)
from packages.api.responses import ApiResponse
from packages.api.schemas.analytics import (
    AnalyticsSummarySchema,
    FeedbackTrendSchema,
    QueriesPerDaySchema,
    TopFailingQuerySchema,
)
from packages.infrastructure.container import ApplicationContainer

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
)


@router.get(
    "/summary",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[AnalyticsSummarySchema],
    summary="Usage analytics summary",
    description=(
        "Tenant-scoped usage dashboards: queries/day, feedback trends "
        "(thumbs-up/down over time), and the most-thumbs-downed messages "
        "as a pragmatic stand-in for \"top failing queries\" — there's no "
        "structured error/exception log to define failure more strictly."
    ),
)
async def get_analytics_summary(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=50),
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    messages = container.repositories.message()
    feedback = container.repositories.feedback()

    queries_per_day = await messages.count_by_tenant_daily(tenant_id, days=days)
    feedback_trends = await feedback.count_by_rating_daily(tenant_id, days=days)
    top_failing = await feedback.top_negative_feedback_messages(tenant_id, limit=limit)

    return ApiResponse(
        message="Analytics summary retrieved.",
        data=AnalyticsSummarySchema(
            queries_per_day=[QueriesPerDaySchema(**d) for d in queries_per_day],
            feedback_trends=[FeedbackTrendSchema(**d) for d in feedback_trends],
            top_failing_queries=[TopFailingQuerySchema(**d) for d in top_failing],
        ),
    )
