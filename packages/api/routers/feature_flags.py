# Router feature flags
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from packages.api.dependencies import get_scoped_container, require_role
from packages.api.responses import ApiResponse
from packages.api.schemas.feature_flag import (
    CreateFeatureFlagRequestSchema,
    FeatureFlagListResponseSchema,
    FeatureFlagResponseSchema,
    ToggleFeatureFlagRequestSchema,
)
from packages.domain.models.feature_flag import FeatureFlag
from packages.infrastructure.container import ApplicationContainer

router = APIRouter(
    prefix="/feature-flags",
    tags=["Feature Flags"],
    # Dogfoods the dynamic system this router itself manages: while
    # the enable_rbac flag is off (the default), this no-ops like
    # every other require_role() route; once flipped on via the
    # toggle endpoint below, this router is the first place that
    # enforcement becomes observable.
    dependencies=[Depends(require_role("admin"))],
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[FeatureFlagResponseSchema],
    summary="Create a feature flag",
    description=(
        "Creates a flag row — global (tenant_id omitted) or a "
        "tenant-specific override. A tenant override is only "
        "meaningful once a global default with the same key also "
        "exists (see FeatureFlagRepository.get_effective)."
    ),
)
async def create_feature_flag(
    payload: CreateFeatureFlagRequestSchema,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    flags = container.repositories.feature_flag()

    existing = await flags.get_by_key_and_tenant(payload.key, payload.tenant_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A flag for key '{payload.key}' already exists for this scope.",
        )

    created = await flags.create(
        FeatureFlag(
            key=payload.key,
            tenant_id=payload.tenant_id,
            enabled=payload.enabled,
            description=payload.description,
        )
    )

    return ApiResponse(
        message="Feature flag created.",
        data=FeatureFlagResponseSchema.model_validate(created),
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[FeatureFlagListResponseSchema],
    summary="List feature flags",
    description="Lists every flag row — global defaults and tenant-specific overrides.",
)
async def list_feature_flags(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    container: ApplicationContainer = Depends(get_scoped_container),
):
    flags = container.repositories.feature_flag()

    rows = await flags.list_all(limit=limit, offset=offset)

    return ApiResponse(
        message="Feature flags retrieved.",
        data=FeatureFlagListResponseSchema(
            total=len(rows),
            limit=limit,
            offset=offset,
            feature_flags=[FeatureFlagResponseSchema.model_validate(r) for r in rows],
        ),
    )


@router.get(
    "/{flag_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[FeatureFlagResponseSchema],
    summary="Fetch a feature flag",
)
async def get_feature_flag(
    flag_id: UUID,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    flags = container.repositories.feature_flag()
    flag = await flags.get(flag_id)

    if flag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature flag not found.")

    return ApiResponse(
        message="Feature flag retrieved.",
        data=FeatureFlagResponseSchema.model_validate(flag),
    )


@router.patch(
    "/{flag_id}/toggle",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[FeatureFlagResponseSchema],
    summary="Toggle a feature flag",
    description=(
        "Flips a flag on/off — takes effect for new reads within "
        "FeatureFlagService's ~30s cache TTL, no redeploy needed. The "
        "first PATCH endpoint in this codebase."
    ),
)
async def toggle_feature_flag(
    flag_id: UUID,
    payload: ToggleFeatureFlagRequestSchema,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    flags = container.repositories.feature_flag()
    flag = await flags.get(flag_id)

    if flag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature flag not found.")

    flag.enabled = payload.enabled
    updated = await flags.update(flag)

    service = container.feature_flags.service()
    service.invalidate(updated.key, updated.tenant_id)

    return ApiResponse(
        message="Feature flag updated.",
        data=FeatureFlagResponseSchema.model_validate(updated),
    )
