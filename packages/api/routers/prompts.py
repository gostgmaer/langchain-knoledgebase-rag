# Router prompts
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
from packages.api.schemas.prompt import (
    CreatePromptRequestSchema,
    PromptListResponseSchema,
    PromptResponseSchema,
)
from packages.api.schemas.prompt_version import (
    CreatePromptVersionRequestSchema,
    PromptVersionListResponseSchema,
    PromptVersionResponseSchema,
)
from packages.domain.models.prompt import Prompt
from packages.domain.models.prompt_version import PromptVersion
from packages.infrastructure.container import ApplicationContainer

router = APIRouter(
    prefix="/prompts",
    tags=["Prompts"],
    dependencies=[Depends(require_admin())],
)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "prompt"


async def _to_response(prompt: Prompt, container: ApplicationContainer) -> PromptResponseSchema:
    prompt_versions = container.repositories.prompt_version()
    published = await prompt_versions.get_published(prompt.id)
    response = PromptResponseSchema.model_validate(prompt)
    response.published_version = (
        PromptVersionResponseSchema.model_validate(published) if published is not None else None
    )
    return response


async def _get_owned_prompt(
    prompt_id: UUID,
    tenant_id: UUID,
    container: ApplicationContainer,
) -> Prompt:
    prompt = await container.repositories.prompt().get(prompt_id)
    if prompt is None or prompt.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found.",
        )
    return prompt


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[PromptResponseSchema],
    dependencies=[Depends(require_admin()), Depends(require_permission(Permission.PROMPTS_WRITE))],
    summary="Create a prompt",
    description=(
        "Creates a new prompt's metadata for the calling tenant. Add its actual text with "
        "POST /prompts/{id}/versions."
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

    await container.audit().record(
        tenant_id=tenant_id,
        actor_id=require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID),
        action="prompt.created",
        resource_type="prompt",
        resource_id=created.id,
        detail={"name": created.name},
    )

    return ApiResponse(
        message="Prompt created.",
        data=await _to_response(created, container),
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[PromptListResponseSchema],
    dependencies=[Depends(require_permission(Permission.PROMPTS_READ))],
    summary="List prompts",
    description="Lists the calling tenant's prompts, any status, each with its currently-published version if it has one.",
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
            prompts=[await _to_response(p, container) for p in rows],
        ),
    )


@router.get(
    "/{prompt_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[PromptResponseSchema],
    dependencies=[Depends(require_permission(Permission.PROMPTS_READ))],
    summary="Fetch a prompt",
    description="Fetches a single prompt's metadata by ID, with its currently-published version if it has one.",
)
async def get_prompt(
    prompt_id: UUID,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    prompt = await _get_owned_prompt(prompt_id, tenant_id, container)

    return ApiResponse(
        message="Prompt retrieved.",
        data=await _to_response(prompt, container),
    )


@router.get(
    "/{prompt_id}/versions",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[PromptVersionListResponseSchema],
    dependencies=[Depends(require_permission(Permission.PROMPTS_READ))],
    summary="List a prompt's versions",
    description="Every version of this prompt's template, most recent first — the full edit history.",
)
async def list_prompt_versions(
    prompt_id: UUID,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    await _get_owned_prompt(prompt_id, tenant_id, container)

    versions = await container.repositories.prompt_version().list_by_prompt(prompt_id)

    return ApiResponse(
        message="Prompt versions retrieved.",
        data=PromptVersionListResponseSchema(
            versions=[PromptVersionResponseSchema.model_validate(v) for v in versions],
        ),
    )


@router.post(
    "/{prompt_id}/versions",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[PromptVersionResponseSchema],
    dependencies=[Depends(require_admin()), Depends(require_permission(Permission.PROMPTS_WRITE))],
    summary="Add a new draft version",
    description=(
        "Adds a new, numbered DRAFT version with real template text — publish it "
        "(POST .../versions/{version_id}/publish) to make it the one live version chat actually "
        "uses. Earlier versions are never overwritten, only superseded, so rolling back is just "
        "publishing an older one again."
    ),
)
async def create_prompt_version(
    prompt_id: UUID,
    payload: CreatePromptVersionRequestSchema,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    await _get_owned_prompt(prompt_id, tenant_id, container)

    prompt_versions = container.repositories.prompt_version()
    next_version = await prompt_versions.next_version_number(prompt_id)

    version = PromptVersion(
        prompt_id=prompt_id,
        version=next_version,
        template=payload.template,
        variables=payload.variables,
        examples=payload.examples,
        changelog=payload.changelog,
    )

    created = await prompt_versions.create(version)

    await container.audit().record(
        tenant_id=tenant_id,
        actor_id=require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID),
        action="prompt_version.created",
        resource_type="prompt",
        resource_id=prompt_id,
        detail={"version": next_version},
    )

    return ApiResponse(
        message=f"Version {next_version} created.",
        data=PromptVersionResponseSchema.model_validate(created),
    )


@router.post(
    "/{prompt_id}/versions/{version_id}/publish",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[PromptVersionResponseSchema],
    dependencies=[Depends(require_admin()), Depends(require_permission(Permission.PROMPTS_WRITE))],
    summary="Publish a version (or roll back to one)",
    description=(
        "Makes this version the one live version for the prompt, unpublishing whichever version "
        "was live before. The same operation for the newest draft and a rollback — publishing an "
        "older version again is how a rollback actually works here, nothing is deleted or rewritten."
    ),
)
async def publish_prompt_version(
    prompt_id: UUID,
    version_id: UUID,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    await _get_owned_prompt(prompt_id, tenant_id, container)

    prompt_versions = container.repositories.prompt_version()
    version = await prompt_versions.get(version_id)

    if version is None or version.prompt_id != prompt_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt version not found.",
        )

    published = await prompt_versions.publish(prompt_id, version)

    await container.audit().record(
        tenant_id=tenant_id,
        actor_id=require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID),
        action="prompt_version.published",
        resource_type="prompt",
        resource_id=prompt_id,
        detail={"version": published.version},
    )

    return ApiResponse(
        message=f"Version {published.version} is now published.",
        data=PromptVersionResponseSchema.model_validate(published),
    )
