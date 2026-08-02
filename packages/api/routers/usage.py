# Router usage
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    get_scoped_container,
    require_uuid_header,
)
from packages.api.responses import ApiResponse
from packages.api.schemas.usage import DailyUsageSchema, UsageResponseSchema
from packages.infrastructure.container import ApplicationContainer

router = APIRouter(
    prefix="/usage",
    tags=["Usage"],
)


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[UsageResponseSchema],
    summary="Token usage and cost totals",
    description=(
        "Tenant-scoped token/cost totals plus a daily breakdown over the "
        "requested window. No cross-tenant aggregate exists — matches this "
        "app's existing architecture, every resource is scoped by "
        "X-Tenant-ID and there is no list-all-tenants endpoint."
    ),
)
async def get_usage(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    messages = container.repositories.message()

    totals = await messages.sum_usage_by_tenant(tenant_id)
    daily = await messages.sum_usage_by_tenant_daily(tenant_id, days=days)

    return ApiResponse(
        message="Usage retrieved.",
        data=UsageResponseSchema(
            **totals,
            daily=[DailyUsageSchema(**d) for d in daily],
        ),
    )
