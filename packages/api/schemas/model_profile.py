# Schema model profile
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateModelProfileRequestSchema(BaseModel):
    """
    Incoming request to create a model profile. `vector` is not a
    request field — it's an internal, currently-unused pgvector column
    on the domain model (populated with a zero-vector placeholder by
    the router, matching packages/conversation/bootstrap.py's own
    default-profile seeding).
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    name: str = Field(min_length=1, max_length=100)

    provider: str = Field(min_length=1, max_length=50)

    model: str = Field(min_length=1, max_length=150)

    description: str | None = Field(default=None, max_length=2000)

    temperature: float = Field(default=0.2, ge=0, le=2)

    top_p: float = Field(default=0.95, gt=0, le=1)

    top_k: int | None = None

    max_tokens: int = Field(default=4096, gt=0)

    context_window: int = Field(gt=0)

    embedding_dimensions: int = Field(default=0, ge=0)

    supports_streaming: bool = True

    supports_tools: bool = True

    supports_reasoning: bool = False

    supports_images: bool = False

    supports_embeddings: bool = False

    is_default: bool = False


class ModelProfileResponseSchema(BaseModel):
    """A single model profile's configuration."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    name: str
    provider: str
    model: str
    description: str | None
    temperature: float
    top_p: float
    top_k: int | None
    max_tokens: int
    context_window: int
    embedding_dimensions: int
    supports_streaming: bool
    supports_tools: bool
    supports_reasoning: bool
    supports_images: bool
    supports_embeddings: bool
    is_default: bool
    status: str


class ModelProfileListResponseSchema(BaseModel):
    """A page of model profiles."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    total: int
    limit: int
    offset: int
    model_profiles: list[ModelProfileResponseSchema]
