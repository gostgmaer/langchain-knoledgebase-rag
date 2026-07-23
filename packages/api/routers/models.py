# Router models
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from packages.api.dependencies import get_scoped_container
from packages.api.responses import ApiResponse
from packages.api.schemas.model_profile import (
    CreateModelProfileRequestSchema,
    ModelProfileListResponseSchema,
    ModelProfileResponseSchema,
)
from packages.config.loader import settings
from packages.domain.enums.model_status import ModelStatus
from packages.domain.models.model_profile import ModelProfile
from packages.infrastructure.container import ApplicationContainer

router = APIRouter(
    prefix="/model-profiles",
    tags=["Model Profiles"],
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[ModelProfileResponseSchema],
    summary="Create a model profile",
    description=(
        "Creates a reusable LLM configuration that agents can reference. "
        "Not tenant-scoped — model profiles are shared, global reference data."
    ),
)
async def create_model_profile(
    payload: CreateModelProfileRequestSchema,
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

    return ApiResponse(
        message="Model profile created.",
        data=ModelProfileResponseSchema.model_validate(created),
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ModelProfileListResponseSchema],
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
