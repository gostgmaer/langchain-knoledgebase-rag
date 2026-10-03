# Schema prompt
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from packages.api.schemas.prompt_version import PromptVersionResponseSchema
from packages.domain.enums.prompt_category import PromptCategory


class CreatePromptRequestSchema(BaseModel):
    """Incoming request to create a prompt."""

    model_config = ConfigDict(
        extra="forbid",
    )

    name: str = Field(min_length=1, max_length=150)

    description: str | None = Field(default=None, max_length=2000)

    category: PromptCategory


class PromptResponseSchema(BaseModel):
    """
    A single prompt's metadata. The actual prompt text lives on PromptVersion
    (see packages/domain/models/prompt.py) — `published_version` is filled in by the router
    (PromptVersion has no direct, reliably-ordered relationship load through this schema alone)
    so a caller doesn't need a second request just to see what's actually live today.
    `GET/POST /prompts/{id}/versions` is the full version history and version-create surface
    (docs/BUGS.md item 30).
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    tenant_id: UUID
    name: str
    slug: str
    description: str | None
    category: str
    is_active: bool
    published_version: PromptVersionResponseSchema | None = None


class PromptListResponseSchema(BaseModel):
    """A page of a tenant's prompts."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    total: int
    limit: int
    offset: int
    prompts: list[PromptResponseSchema]
