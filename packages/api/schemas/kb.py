# Schema kb
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateKnowledgeBaseRequestSchema(BaseModel):
    """Incoming request to create a knowledge base."""

    model_config = ConfigDict(
        extra="forbid",
    )

    name: str = Field(min_length=1, max_length=255)

    description: str | None = Field(default=None, max_length=2000)

    is_public: bool = False


class KnowledgeBaseResponseSchema(BaseModel):
    """A single knowledge base's metadata."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    tenant_id: UUID
    name: str
    slug: str
    description: str | None
    status: str
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    chunk_size: int
    chunk_overlap: int
    similarity_metric: str
    search_type: str
    max_results: int
    is_public: bool
    document_count: int = 0


class KnowledgeBaseListResponseSchema(BaseModel):
    """A page of a tenant's knowledge bases."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    total: int
    limit: int
    offset: int
    knowledge_bases: list[KnowledgeBaseResponseSchema]
