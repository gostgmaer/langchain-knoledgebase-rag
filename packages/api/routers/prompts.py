# Router prompts
from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    get_scoped_container,
    require_uuid_header,
)
from packages.api.responses import ApiResponse
from packages.api.schemas.prompt import (
    CreatePromptRequestSchema,
    PromptListResponseSchema,
    PromptResponseSchema,
)
from packages.domain.models.prompt import Prompt
from packages.infrastructure.container import ApplicationContainer

router = APIRouter(
    prefix="/prompts",
    tags=["Prompts"],
)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "prompt"


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[PromptResponseSchema],
    summary="Create a prompt",
    description=(
        "Creates a new prompt's metadata for the calling tenant. Does not "
        "create a PromptVersion (the actual prompt text) — that has no "
        "repository/API surface yet."
    ),
)
async def create_prompt(
    payload: CreatePromptRequestSchema,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    prompts = container.repositories.prompt()

    slug = _slugify(payload.name)

    existing = await prompts.get_by_tenant_and_slug(tenant_id, slug)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A prompt named '{payload.name}' already exists for this tenant.",
        )

    prompt = Prompt(
        tenant_id=tenant_id,
        name=payload.name,
        slug=slug,
        description=payload.description,
        category=payload.category,
        is_active=True,
    )

    created = await prompts.create(prompt)

    return ApiResponse(
        message="Prompt created.",
        data=PromptResponseSchema.model_validate(created),
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[PromptListResponseSchema],
    summary="List prompts",
    description="Lists the calling tenant's prompts, any status.",
)
async def list_prompts(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    prompts = container.repositories.prompt()

    total = await prompts.count_by_tenant(tenant_id)
    rows = await prompts.list_by_tenant(tenant_id, limit=limit, offset=offset)

    return ApiResponse(
        message="Prompts retrieved.",
        data=PromptListResponseSchema(
            total=total,
            limit=limit,
            offset=offset,
            prompts=[PromptResponseSchema.model_validate(p) for p in rows],
        ),
    )


@router.get(
    "/{prompt_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[PromptResponseSchema],
    summary="Fetch a prompt",
    description="Fetches a single prompt's metadata by ID.",
)
async def get_prompt(
    prompt_id: UUID,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    prompts = container.repositories.prompt()
    prompt = await prompts.get(prompt_id)

    if prompt is None or prompt.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found.",
        )

    return ApiResponse(
        message="Prompt retrieved.",
        data=PromptResponseSchema.model_validate(prompt),
    )
