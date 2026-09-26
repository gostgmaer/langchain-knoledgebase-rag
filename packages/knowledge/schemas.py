from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from uuid import UUID

# ============================================================
# Ingestion
# ============================================================

ChunkingStrategy = Literal["auto", "recursive", "markdown", "semantic"]


@dataclass(slots=True)
class IngestionRequest:
    tenant_id: UUID
    model_profile_id: UUID
    knowledge_base_id: UUID

    file: Path
    document_name: str

    file_id: str | None = None
    chunking_strategy: ChunkingStrategy = "recursive"
    uploaded_by: UUID | None = None
    document_type: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    visibility: str = "tenant"

    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class IngestionResponse:
    document_id: UUID
    chunk_count: int
    embedding_count: int
    skipped: bool = False
    superseded_document_id: UUID | None = None
    """Set when this ingestion created a new version of an existing document."""


# ============================================================
# Search
# ============================================================

@dataclass(slots=True)
class SearchRequest:
    tenant_id: UUID
    model_profile_id: UUID

    query: str

    limit: int = 5

    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class SearchResult:
    document_id: UUID
    chunk_id: UUID

    chunk_index: int

    content: str

    score: float

    metadata: dict[str, object] = field(default_factory=dict)


# ============================================================
# Citation
# ============================================================

@dataclass(slots=True)
class Citation:
    """Citation returned alongside an AI response."""

    document_id: UUID
    chunk_id: UUID

    chunk_index: int

    score: float


# ============================================================
# Delete
# ============================================================

@dataclass(slots=True)
class DeleteRequest:
    tenant_id: UUID
    document_id: UUID


@dataclass(slots=True)
class DeleteResponse:
    success: bool