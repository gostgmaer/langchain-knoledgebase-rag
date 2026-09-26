from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class RetrievalLogSummarySchema(BaseModel):
    retrieval_id: UUID
    trace_id: str | None
    request_id: str | None
    user_id: UUID | None
    conversation_id: UUID | None
    query_hash: str
    query_length: int
    strategy: str
    top_k: int
    reranking_enabled: bool
    reranker_model: str | None
    candidate_count: int
    selected_count: int
    search_latency_ms: int | None
    rerank_latency_ms: int | None
    latency_ms: int | None
    created_at: datetime


class RetrievalResultSchema(BaseModel):
    """One candidate chunk with everything needed to explain why it was (not) used."""

    chunk_id: UUID
    chunk_index: int
    document_id: UUID
    document_name: str | None
    document_version: int | None
    """Version number of the document row that owned the chunk (None if never re-uploaded)."""
    document_is_current: bool | None
    page_number: int | None
    section: str | None
    chunking_strategy: str | None
    retrieval_rank: int
    retrieval_score: float
    reranker_score: float | None
    final_rank: int | None
    selected_for_context: bool
    reranking_changed_rank: bool | None


class RetrievalLogDetailSchema(RetrievalLogSummarySchema):
    model_profile_id: UUID | None
    min_relevance_score: float | None
    sub_query_count: int
    filters: dict[str, Any]
    results: list[RetrievalResultSchema]


class RetrievalLogListSchema(BaseModel):
    total: int
    limit: int
    offset: int
    retrievals: list[RetrievalLogSummarySchema]
