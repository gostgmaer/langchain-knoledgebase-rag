from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID


# ============================================================
# Ingestion
# ============================================================

@dataclass(slots=True)
class IngestionRequest:
    tenant_id: UUID
    model_profile_id: UUID

    file: Path
    document_name: str

    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class IngestionResponse:
    document_id: UUID
    chunk_count: int
    embedding_count: int


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
# Delete
# ============================================================

@dataclass(slots=True)
class DeleteRequest:
    tenant_id: UUID
    document_id: UUID


@dataclass(slots=True)
class DeleteResponse:
    success: bool