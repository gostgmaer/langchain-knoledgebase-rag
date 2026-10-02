# Retrieval log service
from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.domain.models.retrieval_log import RetrievalLog, RetrievalResultLog
from packages.shared.logging import get_logger

logger = get_logger(__name__)

# Bound the rows written per retrieval so logging can never dominate a request.
MAX_LOGGED_CANDIDATES = 50


@dataclass(slots=True)
class CandidateRecord:
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    retrieval_rank: int
    retrieval_score: float
    vector_score: float | None = None
    keyword_score: float | None = None
    reranker_score: float | None = None
    final_rank: int | None = None
    selected: bool = False


@dataclass(slots=True)
class RetrievalRecord:
    tenant_id: UUID
    query: str
    strategy: str
    top_k: int
    reranking_enabled: bool
    retrieval_id: UUID = field(default_factory=uuid4)
    user_id: UUID | None = None
    conversation_id: UUID | None = None
    model_profile_id: UUID | None = None
    trace_id: str | None = None
    request_id: str | None = None
    sub_query_count: int = 1
    min_relevance_score: float | None = None
    reranker_model: str | None = None
    search_latency_ms: int | None = None
    rerank_latency_ms: int | None = None
    latency_ms: int | None = None
    filters: dict = field(default_factory=dict)
    candidates: list[CandidateRecord] = field(default_factory=list)


def hash_query(query: str) -> str:
    """Stable, non-reversible fingerprint used in logs instead of the raw query."""
    return hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()


class RetrievalLogService:
    """
    Persists retrieval logs. Takes a raw session factory (like FeatureFlagService) so a
    write never shares - or poisons - the request's own transaction.

    Logging is best-effort by design: a failure here is reported and swallowed, never raised
    into the user's answer.
    """

    def __init__(self, session_factory: Callable[[], AsyncSession] | async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def record(self, record: RetrievalRecord) -> None:
        try:
            async with self._session_factory() as session:
                session.add(
                    RetrievalLog(
                        id=record.retrieval_id,
                        tenant_id=record.tenant_id,
                        user_id=record.user_id,
                        conversation_id=record.conversation_id,
                        model_profile_id=record.model_profile_id,
                        trace_id=record.trace_id,
                        request_id=record.request_id,
                        query_hash=hash_query(record.query),
                        query_length=len(record.query),
                        sub_query_count=record.sub_query_count,
                        strategy=record.strategy,
                        top_k=record.top_k,
                        min_relevance_score=record.min_relevance_score,
                        reranking_enabled=record.reranking_enabled,
                        reranker_model=record.reranker_model,
                        candidate_count=len(record.candidates),
                        selected_count=sum(1 for c in record.candidates if c.selected),
                        search_latency_ms=record.search_latency_ms,
                        rerank_latency_ms=record.rerank_latency_ms,
                        latency_ms=record.latency_ms,
                        filters=record.filters,
                    )
                )
                await session.flush()
                # Selected chunks first so the cap can never drop something used in an answer.
                ordered = sorted(record.candidates, key=lambda c: (not c.selected, c.retrieval_rank))
                for c in ordered[:MAX_LOGGED_CANDIDATES]:
                    session.add(
                        RetrievalResultLog(
                            retrieval_id=record.retrieval_id,
                            tenant_id=record.tenant_id,
                            chunk_id=c.chunk_id,
                            document_id=c.document_id,
                            chunk_index=c.chunk_index,
                            retrieval_rank=c.retrieval_rank,
                            retrieval_score=c.retrieval_score,
                            vector_score=c.vector_score,
                            keyword_score=c.keyword_score,
                            reranker_score=c.reranker_score,
                            final_rank=c.final_rank,
                            selected_for_context=c.selected,
                        )
                    )
                await session.commit()
        except Exception as exc:  # noqa: BLE001 - logging must never break retrieval
            logger.warning("Could not persist retrieval log", error=str(exc))

        logger.info(
            "rag.retrieval.completed",
            retrieval_id=str(record.retrieval_id),
            tenant_id=str(record.tenant_id),
            query_hash=hash_query(record.query),
            strategy=record.strategy,
            top_k=record.top_k,
            candidates=len(record.candidates),
            selected=sum(1 for c in record.candidates if c.selected),
            latency_ms=record.latency_ms,
            reranker_model=record.reranker_model,
        )
