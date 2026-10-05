# Router models
from __future__ import annotations

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
from packages.api.schemas.model_profile import (
    CreateModelProfileRequestSchema,
    ModelProfileListResponseSchema,
    ModelProfileResponseSchema,
    UpdateModelProfileRequestSchema,
)
from packages.config.loader import settings
from packages.domain.enums.model_status import ModelStatus
from packages.domain.models.model_profile import ModelProfile
from packages.infrastructure.container import ApplicationContainer

router = APIRouter(
    prefix="/model-profiles",
    tags=["Model Profiles"],
    dependencies=[Depends(require_admin())],
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[ModelProfileResponseSchema],
    dependencies=[Depends(require_permission(Permission.MODELS_WRITE))],
    summary="Create a model profile",
    description=(
        "Creates a reusable LLM configuration that agents can reference. "
        "Not tenant-scoped — model profiles are shared, global reference data."
    ),
)
async def create_model_profile(
    payload: CreateModelProfileRequestSchema,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    model_profiles = container.repositories.model_profile()

    existing = await model_profiles.get_by_name(payload.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A model profile named '{payload.name}' already exists.",
        )

    model_profile = ModelProfile(
        name=payload.name,
        provider=payload.provider,
        model=payload.model,
        description=payload.description,
        temperature=payload.temperature,
        top_p=payload.top_p,
        top_k=payload.top_k,
        max_tokens=payload.max_tokens,
        context_window=payload.context_window,
        embedding_dimensions=payload.embedding_dimensions,
        # Not a real request field — this column has no established
        # meaning for a model profile; zero-filled the same way
        # packages/conversation/bootstrap.py's default profile seeds it.
        vector=[0.0] * settings.embedding.dimensions,
        supports_streaming=payload.supports_streaming,
        supports_tools=payload.supports_tools,
        supports_reasoning=payload.supports_reasoning,
        supports_images=payload.supports_images,
        supports_embeddings=payload.supports_embeddings,
        is_default=payload.is_default,
        status=ModelStatus.ACTIVE,
    )

    created = await model_profiles.create(model_profile)

    # Model profiles have no tenant of their own (shared, global reference data), but
    # AuditEvent.tenant_id is required — DEFAULT_TENANT_ID is the same "no real tenant"
    # sentinel already used wherever a request arrives with no X-Tenant-ID header.
    await container.audit().record(
        tenant_id=DEFAULT_TENANT_ID,
        actor_id=require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID),
        action="model_profile.created",
        resource_type="model_profile",
        resource_id=created.id,
        detail={"name": created.name, "provider": str(created.provider), "model": created.model},
    )

    return ApiResponse(
        message="Model profile created.",
        data=ModelProfileResponseSchema.model_validate(created),
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ModelProfileListResponseSchema],
    dependencies=[Depends(require_permission(Permission.MODELS_READ))],
    summary="List model profiles",
    description="Lists all model profiles.",
)
async def list_model_profiles(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    container: ApplicationContainer = Depends(get_scoped_container),
):
    model_profiles = container.repositories.model_profile()

    total = await model_profiles.count()
    rows = await model_profiles.list(limit=limit, offset=offset)

    return ApiResponse(
        message="Model profiles retrieved.",
        data=ModelProfileListResponseSchema(
            total=total,
            limit=limit,
            offset=offset,
            model_profiles=[ModelProfileResponseSchema.model_validate(m) for m in rows],
        ),
    )


@router.get(
    "/{model_profile_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ModelProfileResponseSchema],
    dependencies=[Depends(require_permission(Permission.MODELS_READ))],
    summary="Fetch a model profile",
    description="Fetches a single model profile by ID.",
)
async def get_model_profile(
    model_profile_id: UUID,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    model_profiles = container.repositories.model_profile()
    model_profile = await model_profiles.get(model_profile_id)

    if model_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model profile not found.",
        )

    return ApiResponse(
        message="Model profile retrieved.",
        data=ModelProfileResponseSchema.model_validate(model_profile),
    )


@router.patch(
    "/{model_profile_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ModelProfileResponseSchema],
    dependencies=[Depends(require_permission(Permission.MODELS_WRITE))],
    summary="Edit a model profile",
    description="Partial update — only the fields sent are changed.",
)
async def update_model_profile(
    model_profile_id: UUID,
    payload: UpdateModelProfileRequestSchema,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    model_profiles = container.repositories.model_profile()
    model_profile = await model_profiles.get(model_profile_id)

    if model_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model profile not found.",
        )

    updates = payload.model_dump(exclude_unset=True)

    if "name" in updates and updates["name"] != model_profile.name:
        existing = await model_profiles.get_by_name(updates["name"])
        if existing is not None and existing.id != model_profile.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A model profile named '{updates['name']}' already exists.",
            )

    for field, value in updates.items():
        setattr(model_profile, field, value)

    updated = await model_profiles.update(model_profile)

    await container.audit().record(
        tenant_id=DEFAULT_TENANT_ID,
        actor_id=require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID),
        action="model_profile.updated",
        resource_type="model_profile",
        resource_id=updated.id,
        detail={"name": updated.name, "fields": sorted(updates)},
    )

    return ApiResponse(
        message="Model profile updated.",
        data=ModelProfileResponseSchema.model_validate(updated),
    )
