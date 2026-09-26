# Router retrieval settings
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    DEFAULT_USER_ID,
    get_scoped_container,
    require_admin,
    require_uuid_header,
)
from packages.api.responses import ApiResponse
from packages.application.services.retrieval_settings_service import (
    MAX_RESULTS_RANGE,
    MIN_RELEVANCE_RANGE,
    RetrievalOverrides,
    merge,
    platform_defaults,
)
from packages.config.loader import settings
from packages.infrastructure.container import ApplicationContainer

router = APIRouter(
    prefix="/retrieval-settings",
    tags=["Retrieval Settings"],
    dependencies=[Depends(require_admin())],
)


class RetrievalValuesSchema(BaseModel):
    max_results: int
    min_relevance_score: float
    reranking_enabled: bool


class RetrievalSettingsResponseSchema(BaseModel):
    effective: RetrievalValuesSchema
    """What retrieval uses right now for this workspace."""
    overrides: dict[str, int | float | bool | None]
    """Only the values this workspace changed; null = using the platform default."""
    defaults: RetrievalValuesSchema
    """The platform (environment) defaults."""
    retrieval_strategy: str
    """Fixed platform-wide (RETRIEVAL_STRATEGY); shown for information, not editable here."""


class RetrievalSettingsUpdateSchema(BaseModel):
    """Replaces this workspace's overrides. A field left null goes back to the platform default."""

    model_config = ConfigDict(extra="forbid")

    max_results: int | None = Field(default=None, ge=MAX_RESULTS_RANGE[0], le=MAX_RESULTS_RANGE[1])
    min_relevance_score: float | None = Field(default=None, ge=MIN_RELEVANCE_RANGE[0], le=MIN_RELEVANCE_RANGE[1])
    reranking_enabled: bool | None = None


def _response(overrides: RetrievalOverrides) -> RetrievalSettingsResponseSchema:
    def values(v) -> RetrievalValuesSchema:
        return RetrievalValuesSchema(
            max_results=v.max_results, min_relevance_score=v.min_relevance_score, reranking_enabled=v.reranking_enabled
        )

    return RetrievalSettingsResponseSchema(
        effective=values(merge(overrides)),
        overrides={
            "max_results": overrides.max_results,
            "min_relevance_score": overrides.min_relevance_score,
            "reranking_enabled": overrides.reranking_enabled,
        },
        defaults=values(platform_defaults()),
        retrieval_strategy=settings.rag.retrieval_strategy,
    )


@router.get(
    "",
    response_model=ApiResponse[RetrievalSettingsResponseSchema],
    summary="How retrieval is configured for this workspace",
)
async def get_retrieval_settings(
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    service = container.graph.retrieval_settings()
    return ApiResponse(message="Retrieval settings retrieved.", data=_response(await service.get_overrides(tenant_id)))


@router.put(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[RetrievalSettingsResponseSchema],
    summary="Change retrieval behaviour for this workspace",
    description=(
        "Sets how many chunks answers use (`max_results`), the reranker score below which weaker chunks "
        "are dropped (`min_relevance_score`; the best chunk is always kept), and whether the cross-encoder "
        "reranker runs (`reranking_enabled`). Takes effect within about 30 seconds and is audited. "
        "With reranking off, chunks are ranked by their search score and the relevance floor does not apply."
    ),
)
async def update_retrieval_settings(
    payload: RetrievalSettingsUpdateSchema,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    user_id = require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID)
    service = container.graph.retrieval_settings()

    before = await service.get_overrides(tenant_id)
    after = RetrievalOverrides(payload.max_results, payload.min_relevance_score, payload.reranking_enabled)
    await service.save(tenant_id, after, user_id)

    changed = {
        name: {"from": getattr(before, name), "to": getattr(after, name)}
        for name in ("max_results", "min_relevance_score", "reranking_enabled")
        if getattr(before, name) != getattr(after, name)
    }
    if changed:
        await container.audit().record(
            tenant_id=tenant_id,
            actor_id=user_id,
            action="retrieval_settings.changed",
            resource_type="retrieval_settings",
            detail=changed,
        )

    return ApiResponse(message="Retrieval settings saved.", data=_response(after))
