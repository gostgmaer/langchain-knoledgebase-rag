"""
packages/graph/nodes/retrieve.py
"""

from __future__ import annotations

import asyncio
import time

import structlog

from packages.application.services.retrieval_log_service import (
    CandidateRecord,
    RetrievalLogService,
    RetrievalRecord,
)
from packages.config.loader import settings
from packages.graph.state import GraphState
from packages.knowledge.manager import KnowledgeManager
from packages.knowledge.reranking.cross_encoder import (
    CrossEncoderReranker,
    apply_relevance_floor,
)
from packages.knowledge.schemas import Citation
from packages.knowledge.schemas import SearchResult as FlatSearchResult
from packages.knowledge.vectorstores.schema import SearchFilter, SearchOptions

# Candidate pool fetched per sub-query, before merge + rerank narrows
# down to settings.rag.max_results.
CANDIDATE_LIMIT = 10


class RetrieveNode:
    """
    Retrieves relevant knowledge for the current user query.

    Responsibilities:
    - Search the knowledge base using the planner's rewritten/expanded
      queries (falling back to the raw last message if the planner
      didn't run or found no query to rewrite)
    - Merge and dedupe multi-query results by chunk id
    - Rerank the merged candidates via a cross-encoder
    - Update graph state with context, flat search results, and
      citations

    This node does not build prompts or invoke the LLM.
    """

    def __init__(
        self,
        knowledge_manager: KnowledgeManager,
        reranker: CrossEncoderReranker,
        retrieval_log: RetrievalLogService | None = None,
    ) -> None:
        self._knowledge = knowledge_manager
        self._reranker = reranker
        self._retrieval_log = retrieval_log

    async def __call__(
        self,
        state: GraphState,
    ) -> GraphState:

        started = time.perf_counter()
        primary_query = state.get("rewritten_query") or state["messages"][-1].content
        queries = [primary_query, *state.get("expanded_queries", [])]

        filters = SearchFilter(
            tenant_id=state["tenant_id"],
            model_profile_id=state["model_profile_id"],
        )

        # Independent sub-queries, fetched concurrently rather than
        # awaited one at a time — none depends on another's result,
        # only the merge below does (Advanced LangGraph's "Parallel
        # Execution", docs/mvpRAG.md v2.0).
        per_query_results = await asyncio.gather(
            *(
                self._knowledge.search(
                    query=query,
                    filters=filters,
                    options=SearchOptions(limit=CANDIDATE_LIMIT),
                )
                for query in queries
            )
        )

        search_done = time.perf_counter()
        merged: dict[object, object] = {}

        for results in per_query_results:
            for result in results:
                existing = merged.get(result.chunk.id)
                if existing is None or result.score > existing.score:
                    merged[result.chunk.id] = result

        candidates = list(merged.values())

        top_k = settings.rag.max_results

        rerank_started = time.perf_counter()
        reranked = await self._reranker.rerank(
            primary_query,
            candidates,
            top_k=top_k,
        )
        rerank_done = time.perf_counter()

        reranked = apply_relevance_floor(reranked, settings.rag.min_relevance_score)

        retrieval_id = await self._log_retrieval(
            state,
            primary_query=primary_query,
            query_count=len(queries),
            candidates=candidates,
            reranked=reranked,
            top_k=top_k,
            search_ms=int((search_done - started) * 1000),
            rerank_ms=int((rerank_done - rerank_started) * 1000),
            total_ms=int((time.perf_counter() - started) * 1000),
        )
        state["retrieval_id"] = retrieval_id

        state["context"] = [result.chunk.content for result in reranked]

        state["search_results"] = [
            FlatSearchResult(
                document_id=result.chunk.document_id,
                chunk_id=result.chunk.id,
                chunk_index=result.chunk.chunk_index,
                content=result.chunk.content,
                score=result.score,
            )
            for result in reranked
        ]

        state["citations"] = [
            Citation(
                document_id=result.chunk.document_id,
                chunk_id=result.chunk.id,
                chunk_index=result.chunk.chunk_index,
                score=result.score,
            )
            for result in reranked
        ]

        return state

    async def _log_retrieval(
        self,
        state: GraphState,
        *,
        primary_query: str,
        query_count: int,
        candidates: list,
        reranked: list,
        top_k: int,
        search_ms: int,
        rerank_ms: int,
        total_ms: int,
    ):
        """Records this retrieval (ids and scores only). Returns its retrieval id, or None when logging is off."""
        if self._retrieval_log is None:
            return None

        context = structlog.contextvars.get_contextvars()
        by_rerank = {r.chunk.id: (rank, r.score) for rank, r in enumerate(reranked, start=1)}
        ordered = sorted(candidates, key=lambda r: r.score, reverse=True)

        record = RetrievalRecord(
            tenant_id=state["tenant_id"],
            user_id=state.get("user_id"),
            conversation_id=state.get("conversation_id"),
            model_profile_id=state.get("model_profile_id"),
            trace_id=context.get("trace_id"),
            request_id=context.get("request_id"),
            query=primary_query,
            sub_query_count=query_count,
            strategy=settings.rag.retrieval_strategy,
            top_k=top_k,
            min_relevance_score=settings.rag.min_relevance_score,
            reranking_enabled=True,
            reranker_model=getattr(self._reranker, "_model_name", None),
            search_latency_ms=search_ms,
            rerank_latency_ms=rerank_ms,
            latency_ms=total_ms,
            filters={"tenant_scoped": True},
            candidates=[
                CandidateRecord(
                    chunk_id=r.chunk.id,
                    document_id=r.chunk.document_id,
                    chunk_index=r.chunk.chunk_index,
                    retrieval_rank=position,
                    retrieval_score=float(r.score),
                    reranker_score=by_rerank[r.chunk.id][1] if r.chunk.id in by_rerank else None,
                    final_rank=by_rerank[r.chunk.id][0] if r.chunk.id in by_rerank else None,
                    selected=r.chunk.id in by_rerank,
                )
                for position, r in enumerate(ordered, start=1)
            ],
        )
        await self._retrieval_log.record(record)
        return record.retrieval_id
