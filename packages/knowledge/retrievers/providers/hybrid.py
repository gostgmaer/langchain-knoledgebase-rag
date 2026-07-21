# hybrid.py
from __future__ import annotations

import asyncio
import re

from rank_bm25 import BM25Okapi

from packages.knowledge.retrievers.base import BaseRetriever
from packages.knowledge.retrievers.schemas import RetrievalRequest
from packages.knowledge.vectorstores.manager import VectorStoreManager
from packages.knowledge.vectorstores.schema import SearchResult

RRF_K = 60

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())


class HybridRetriever(BaseRetriever):
    """
    Fuses dense vector search with BM25 keyword search via reciprocal
    rank fusion, so exact-match terms (product codes, acronyms) that
    dense embeddings tend to blur are still surfaced.

    The BM25 index is rebuilt from scratch on every call over a
    bounded candidate pool fetched from the vector store — acceptable
    at current data scale, would need a persisted/incremental index
    at real production scale.
    """

    def __init__(
        self,
        vector_store: VectorStoreManager,
        candidate_pool_size: int = 500,
    ) -> None:
        self.vector_store = vector_store
        self.candidate_pool_size = candidate_pool_size

    async def retrieve(
        self,
        request: RetrievalRequest,
    ) -> list[SearchResult]:

        limit = request.options.limit if request.options else 5

        vector_results = await self.vector_store.similarity_search(
            query_embedding=request.query_embedding,
            filters=request.filters,
            options=request.options,
        )

        if not request.query.strip():
            return vector_results

        candidates = await self.vector_store.list_chunks(
            filters=request.filters,
            limit=self.candidate_pool_size,
        )

        if not candidates:
            return vector_results

        keyword_results = await asyncio.to_thread(
            self._bm25_rank,
            request.query,
            candidates,
        )

        return self._reciprocal_rank_fusion(
            vector_results,
            keyword_results,
            limit=limit,
        )

    def _bm25_rank(
        self,
        query: str,
        candidates: list[SearchResult],
    ) -> list[SearchResult]:

        tokenized_corpus = [
            _tokenize(candidate.chunk.content) for candidate in candidates
        ]

        bm25 = BM25Okapi(tokenized_corpus)

        scores = bm25.get_scores(_tokenize(query))

        ranked = sorted(
            zip(scores, candidates),
            key=lambda pair: pair[0],
            reverse=True,
        )

        return [
            SearchResult(chunk=candidate.chunk, score=float(score))
            for score, candidate in ranked
            if score > 0
        ]

    def _reciprocal_rank_fusion(
        self,
        vector_results: list[SearchResult],
        keyword_results: list[SearchResult],
        *,
        limit: int,
    ) -> list[SearchResult]:

        fused_scores: dict[object, float] = {}
        chunks: dict[object, SearchResult] = {}

        for ranked_list in (vector_results, keyword_results):
            for rank, result in enumerate(ranked_list):
                chunk_id = result.chunk.id
                fused_scores[chunk_id] = (
                    fused_scores.get(chunk_id, 0.0) + 1 / (RRF_K + rank + 1)
                )
                chunks.setdefault(chunk_id, result)

        ordered_ids = sorted(
            fused_scores,
            key=lambda chunk_id: fused_scores[chunk_id],
            reverse=True,
        )

        return [
            SearchResult(chunk=chunks[chunk_id].chunk, score=fused_scores[chunk_id])
            for chunk_id in ordered_ids[:limit]
        ]
