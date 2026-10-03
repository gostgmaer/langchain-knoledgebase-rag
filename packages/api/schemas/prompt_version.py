# Schema prompt version
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreatePromptVersionRequestSchema(BaseModel):
    """Incoming request to add a new draft version to an existing prompt."""

    model_config = ConfigDict(
        extra="forbid",
    )

    template: str = Field(min_length=1)

    variables: dict[str, Any] = Field(default_factory=dict)

    examples: list[dict[str, Any]] = Field(default_factory=list)

    changelog: str | None = Field(default=None, max_length=2000)


class PromptVersionResponseSchema(BaseModel):
    """One immutable version of a prompt's template."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    prompt_id: UUID
    version: int
    status: str
    template: str
    variables: dict[str, Any]
    examples: list[dict[str, Any]]
    changelog: str | None
    is_published: bool
    is_default: bool
    created_at: datetime


class PromptVersionListResponseSchema(BaseModel):
    """Every version of one prompt, most recent first."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    versions: list[PromptVersionResponseSchema]
