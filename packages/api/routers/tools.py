# Router tools
from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    DEFAULT_USER_ID,
    get_scoped_container,
    require_admin,
    require_permission,
    require_uuid_header,
)
from packages.api.permissions import Permission
from packages.api.responses import ApiResponse
from packages.api.schemas.tool import (
    CreateToolRequestSchema,
    ToolListResponseSchema,
    ToolResponseSchema,
)
from packages.domain.enums.tool_status import ToolStatus
from packages.domain.models.tool import Tool
from packages.infrastructure.container import ApplicationContainer

router = APIRouter(
    prefix="/tool-definitions",
    tags=["Tool Definitions"],
    dependencies=[Depends(require_admin())],
)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "tool"


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[ToolResponseSchema],
    dependencies=[Depends(require_admin()), Depends(require_permission(Permission.TOOLS_WRITE))],
    summary="Register a tool definition",
    description=(
        "Creates a new tool definition for the calling tenant. A CUSTOM-category row with "
        "configuration.url becomes a real, callable webhook tool in chat (packages/tools/"
        "webhook.py, docs/BUGS.md item 29) — every other category is metadata only, since "
        "packages/tools/builtin/ already has fixed, code-defined implementations for those."
    ),
)
async def create_tool(
    payload: CreateToolRequestSchema,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    tools = container.repositories.tool()

    slug = _slugify(payload.name)

    existing = await tools.get_by_tenant_and_slug(tenant_id, slug)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A tool named '{payload.name}' already exists for this tenant.",
        )

    tool = Tool(
        tenant_id=tenant_id,
        name=payload.name,
        slug=slug,
        description=payload.description,
        category=payload.category,
        provider=payload.provider,
        configuration=payload.configuration,
        timeout_seconds=payload.timeout_seconds,
        retry_count=payload.retry_count,
        is_active=True,
        status=ToolStatus.ACTIVE,
    )

    created = await tools.create(tool)

    await container.audit().record(
        tenant_id=tenant_id,
        actor_id=require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID),
        action="tool.created",
        resource_type="tool",
        resource_id=created.id,
        detail={"name": created.name, "category": str(created.category)},
    )

    return ApiResponse(
        message="Tool definition created.",
        data=ToolResponseSchema.model_validate(created),
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ToolListResponseSchema],
    dependencies=[Depends(require_permission(Permission.TOOLS_READ))],
    summary="List tool definitions",
    description="Lists the calling tenant's tool definitions, any status.",
)
async def list_tools(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    tools = container.repositories.tool()

    total = await tools.count_by_tenant(tenant_id)
    rows = await tools.list_by_tenant(tenant_id, limit=limit, offset=offset)

    return ApiResponse(
        message="Tool definitions retrieved.",
        data=ToolListResponseSchema(
            total=total,
            limit=limit,
            offset=offset,
            tools=[ToolResponseSchema.model_validate(t) for t in rows],
        ),
    )


@router.get(
    "/{tool_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ToolResponseSchema],
    dependencies=[Depends(require_permission(Permission.TOOLS_READ))],
    summary="Fetch a tool definition",
    description="Fetches a single tool definition's metadata by ID.",
)
async def get_tool(
    tool_id: UUID,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    tools = container.repositories.tool()
    tool = await tools.get(tool_id)

    if tool is None or tool.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool definition not found.",
        )

    return ApiResponse(
        message="Tool definition retrieved.",
        data=ToolResponseSchema.model_validate(tool),
    )
