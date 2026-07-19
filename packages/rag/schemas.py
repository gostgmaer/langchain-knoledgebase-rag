# schemas.py
"""
RAG schemas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from packages.knowledge.retrievers.schemas import SearchResult


# ============================================================
# Request
# ============================================================


@dataclass(slots=True)
class RAGRequest:
    """
    Request for generating an AI response using RAG.
    """

    tenant_id: UUID

    model_profile_id: UUID

    query: str

    conversation_id: UUID | None = None

    system_prompt: str | None = None

    metadata: dict[str, object] = field(default_factory=dict)


# ============================================================
# Citation
# ============================================================


@dataclass(slots=True)
class Citation:
    """
    Citation returned with an AI response.
    """

    document_id: UUID

    chunk_id: UUID

    chunk_index: int

    score: float


# ============================================================
# Context
# ============================================================


@dataclass(slots=True)
class Context:
    """
    Context built from retrieved search results.
    """

    text: str

    search_results: list[SearchResult]


# ============================================================
# Response
# ============================================================


@dataclass(slots=True)
class RAGResponse:
    """
    Final response returned by the RAG pipeline.
    """

    answer: str

    context: Context

    citations: list[Citation]

    metadata: dict[str, object] = field(default_factory=dict)