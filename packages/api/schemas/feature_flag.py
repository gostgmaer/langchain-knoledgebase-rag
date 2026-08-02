from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CreateFeatureFlagRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    tenant_id: UUID | None = None
    enabled: bool = False
    description: str | None = None


class ToggleFeatureFlagRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class FeatureFlagResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    key: str
    tenant_id: UUID | None
    enabled: bool
    description: str | None


class FeatureFlagListResponseSchema(BaseModel):
    total: int
    limit: int
    offset: int
    feature_flags: list[FeatureFlagResponseSchema]
