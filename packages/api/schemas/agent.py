# Schema agent
from __future__ import annotations

from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _validate_origins(origins: list[str] | None) -> list[str] | None:
    if origins is None:
        return None
    for origin in origins:
        parts = urlsplit(origin)
        if parts.scheme not in ("http", "https") or not parts.netloc or parts.path:
            raise ValueError(f"'{origin}' must be an origin like https://example.com, with no path.")
    return origins


class CreateAgentRequestSchema(BaseModel):
    """Incoming request to create an agent."""

    model_config = ConfigDict(
        extra="forbid",
    )

    name: str = Field(min_length=1, max_length=255)

    description: str | None = Field(default=None, max_length=2000)

    system_prompt: str = Field(min_length=1)

    llm_provider: str = Field(min_length=1, max_length=50)

    llm_model: str = Field(min_length=1, max_length=100)

    model_profile_id: UUID

    temperature: float = Field(default=0.2, ge=0, le=2)

    top_p: float = Field(default=0.95, ge=0, le=1)

    max_tokens: int = Field(default=4096, gt=0)


class UpdateAgentRequestSchema(BaseModel):
    """Incoming request to edit an existing agent. Every field is optional — only what's sent changes."""

    model_config = ConfigDict(
        extra="forbid",
    )

    name: str | None = Field(default=None, min_length=1, max_length=255)

    description: str | None = Field(default=None, max_length=2000)

    system_prompt: str | None = Field(default=None, min_length=1)

    llm_provider: str | None = Field(default=None, min_length=1, max_length=50)

    llm_model: str | None = Field(default=None, min_length=1, max_length=100)

    model_profile_id: UUID | None = None

    temperature: float | None = Field(default=None, ge=0, le=2)

    top_p: float | None = Field(default=None, ge=0, le=1)

    max_tokens: int | None = Field(default=None, gt=0)

    is_active: bool | None = None

    widget_enabled: bool | None = None

    widget_allowed_origins: list[str] | None = Field(default=None, max_length=20)

    _validate_widget_allowed_origins = field_validator("widget_allowed_origins")(_validate_origins)


class AgentResponseSchema(BaseModel):
    """A single agent's configuration."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    tenant_id: UUID
    name: str
    slug: str
    description: str | None
    system_prompt: str
    llm_provider: str
    llm_model: str
    model_profile_id: UUID
    temperature: float
    top_p: float
    max_tokens: int
    is_active: bool
    status: str
    widget_enabled: bool
    widget_public_id: str | None
    widget_allowed_origins: list[str]


class AgentWidgetRotateResponseSchema(BaseModel):
    """The agent's new widget_public_id after a rotation — the previous one stops working immediately."""

    model_config = ConfigDict(from_attributes=True)

    widget_public_id: str


class AgentListResponseSchema(BaseModel):
    """A page of a tenant's agents."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    total: int
    limit: int
    offset: int
    agents: list[AgentResponseSchema]
