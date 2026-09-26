from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from packages.domain.models.document_chunk import DocumentChunk
from packages.shared.access import can_read_restricted, current_user_id, current_user_roles


@dataclass(slots=True)
class SearchFilter:
    """Filters applied during vector search."""

    tenant_id: UUID
    model_profile_id: UUID

    document_id: UUID | None = None

    chunk_ids: list[UUID] | None = None

    # Access: fail-closed. Defaults to the current request's clearance (False outside a request).
    include_restricted: bool = field(default_factory=can_read_restricted)
    user_id: str | None = field(default_factory=current_user_id)
    user_roles: tuple[str, ...] = field(default_factory=current_user_roles)

    # Metadata filters, applied inside the search query itself.
    knowledge_base_id: UUID | None = None
    document_ids: list[UUID] | None = None
    document_types: list[str] | None = None
    categories: list[str] | None = None
    tags: list[str] | None = None
    """Documents must carry ALL of these tags."""
    language: str | None = None

    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class SearchOptions:
    """Search execution options."""

    limit: int = 5

    score_threshold: float | None = None

    fetch_k: int = 20

    lambda_mult: float = 0.5


@dataclass(slots=True)
class SearchResult:
    """Single search result."""

    chunk: DocumentChunk

    score: float

    # Components behind `score` when the hybrid retriever fused two rankings. None = not from
    # that ranker (or not a hybrid result).
    vector_score: float | None = None
    keyword_score: float | None = None