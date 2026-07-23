# Schema agent
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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


class AgentListResponseSchema(BaseModel):
    """A page of a tenant's agents."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    total: int
    limit: int
    offset: int
    agents: list[AgentResponseSchema]
