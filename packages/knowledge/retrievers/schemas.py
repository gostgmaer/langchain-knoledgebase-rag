from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID


# ============================================================
# Ingestion
# ============================================================

@dataclass(slots=True)
class IngestionRequest:
    """
    Request for ingesting a document into the knowledge base.
    """

    tenant_id: UUID
    model_profile_id: UUID

    file: Path
    document_name: str

    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class IngestionResponse:
    """
    Result of a successful ingestion.
    """

    document_id: UUID
    chunk_count: int
    embedding_count: int


# ============================================================
# Search
# ============================================================

@dataclass(slots=True)
class SearchRequest:
    """
    Search request for the knowledge base.
    """

    tenant_id: UUID
    model_profile_id: UUID

    query: str

    limit: int = 5

    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class SearchResult:
    """
    Search result returned from the knowledge base.
    """

    document_id: UUID

    chunk_id: UUID

    chunk_index: int

    content: str

    score: float

    metadata: dict[str, object] = field(default_factory=dict)


# ============================================================
# Delete
# ============================================================

@dataclass(slots=True)
class DeleteRequest:
    """
    Delete a document from the knowledge base.
    """

    tenant_id: UUID

    document_id: UUID


@dataclass(slots=True)
class DeleteResponse:
    """
    Delete operation result.
    """

    success: bool