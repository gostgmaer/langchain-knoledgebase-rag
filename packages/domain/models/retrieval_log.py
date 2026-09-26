# Retrieval log models
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.domain.models.base import BaseModel


class RetrievalLog(BaseModel):
    """
    One retrieval request: who asked (by tenant/user/conversation), how it ran, and how long it took.

    `id` is the retrieval id. The raw query text is deliberately NOT stored - only its hash
    and length - so the log cannot leak what users typed; the per-chunk rows below hold ids
    and scores, never content.
    """

    __tablename__ = "retrieval_logs"

    __table_args__ = (
        Index("ix_retrieval_log_tenant_created", "tenant_id", "created_at"),
        Index("ix_retrieval_log_conversation", "conversation_id"),
        Index("ix_retrieval_log_trace", "trace_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    conversation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    model_profile_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))

    trace_id: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64))

    query_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    query_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sub_query_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    strategy: Mapped[str] = mapped_column(String(32), nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    min_relevance_score: Mapped[float | None] = mapped_column(Float)
    reranking_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reranker_model: Mapped[str | None] = mapped_column(String(128))

    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    selected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    search_latency_ms: Mapped[int | None] = mapped_column(Integer)
    rerank_latency_ms: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)

    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class RetrievalResultLog(BaseModel):
    """
    One candidate chunk of a retrieval: its score from the search stage, its reranker score,
    where it ended up, and whether it was kept as context for the answer.

    `document_id` is the document row that owned the chunk at retrieval time. Versions are
    separate document rows (see DocumentVersion), so this pins the exact version used.
    """

    __tablename__ = "retrieval_result_logs"

    __table_args__ = (
        Index("ix_retrieval_result_retrieval", "retrieval_id"),
        Index("ix_retrieval_result_chunk", "chunk_id"),
        Index("ix_retrieval_result_document", "document_id"),
    )

    retrieval_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("retrieval_logs.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    chunk_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    retrieval_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    retrieval_score: Mapped[float] = mapped_column(Float, nullable=False)
    reranker_score: Mapped[float | None] = mapped_column(Float)
    final_rank: Mapped[int | None] = mapped_column(Integer)
    selected_for_context: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
