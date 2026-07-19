from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from packages.domain.models.document_chunk import DocumentChunk


@dataclass(slots=True)
class SearchFilter:
    """Filters applied during vector search."""

    tenant_id: UUID
    model_profile_id: UUID

    document_id: UUID | None = None

    chunk_ids: list[UUID] | None = None

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