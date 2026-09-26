# Schema search
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SearchRequestSchema(BaseModel):
    """
    Incoming direct-search request — exposes Phase 9's retrieval to
    clients that want raw search results rather than a chat-mediated
    answer (docs/mvpRAG.md Phase 14's "Search API").
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    query: str = Field(min_length=1, max_length=2000)

    limit: int = Field(default=5, ge=1, le=50)

    document_id: UUID | None = Field(
        default=None,
        description="Scope the search to one document instead of the whole knowledge base.",
    )

    knowledge_base_id: UUID | None = None
    document_types: list[str] | None = Field(default=None, max_length=20)
    categories: list[str] | None = Field(default=None, max_length=20)
    tags: list[str] | None = Field(default=None, max_length=20, description="Documents must carry all of these tags.")
    language: str | None = Field(default=None, max_length=20)


class SearchResultSchema(BaseModel):
    """A single reranked search result."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    document_id: UUID
    chunk_id: UUID
    chunk_index: int
    content: str
    score: float


class SearchResponseSchema(BaseModel):
    """Reranked search results for a direct query."""

    query: str
    results: list[SearchResultSchema]
