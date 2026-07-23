# Schema prompt
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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
    A single prompt's metadata. The actual prompt text lives on
    PromptVersion, not here (see packages/domain/models/prompt.py) —
    versioning has no repository/API surface yet, a separate,
    follow-up gap.
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


class PromptListResponseSchema(BaseModel):
    """A page of a tenant's prompts."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    total: int
    limit: int
    offset: int
    prompts: list[PromptResponseSchema]
