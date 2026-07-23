# Schema tool
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from packages.domain.enums.tool_category import ToolCategory


class CreateToolRequestSchema(BaseModel):
    """
    Incoming request to register a tool definition. Distinct from
    packages/tools/ — the in-process registry that actually powers
    chat tool-calling (packages/tools/manager.py's ToolManager). This
    is a separate, DB-backed record of tool metadata with no runtime
    link to the registry yet.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    name: str = Field(min_length=1, max_length=150)

    description: str | None = Field(default=None, max_length=2000)

    category: ToolCategory

    provider: str = Field(min_length=1, max_length=100)

    configuration: dict[str, Any] = Field(default_factory=dict)

    timeout_seconds: int = Field(default=30, gt=0)

    retry_count: int = Field(default=3, ge=0)


class ToolResponseSchema(BaseModel):
    """A single tool definition's metadata."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    tenant_id: UUID
    name: str
    slug: str
    description: str | None
    category: str
    provider: str
    configuration: dict[str, Any]
    timeout_seconds: int
    retry_count: int
    is_active: bool
    status: str


class ToolListResponseSchema(BaseModel):
    """A page of a tenant's tool definitions."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    total: int
    limit: int
    offset: int
    tools: list[ToolResponseSchema]
