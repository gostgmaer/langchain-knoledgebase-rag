from __future__ import annotations

import asyncio

from packages.knowledge.vectorstores.schema import SearchResult
from packages.shared.logging import get_logger

logger = get_logger(__name__)

DEFAULT_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class CrossEncoderReranker:
    """
    Second-pass reranker scoring (query, chunk) pairs directly via a
    cross-encoder — more accurate than embedding-similarity ranking
    alone, at the cost of real per-call latency.

    The underlying sentence-transformers model is lazy-loaded on
    first use (not in __init__), so constructing this class — and
    wiring it as a DI singleton at container-build time — never
    triggers the ~90MB model download; only the first real rerank()
    call does.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
    ) -> None:
        self._model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            logger.info("Loading cross-encoder reranker model", model=self._model_name)
            self._model = CrossEncoder(self._model_name)

        return self._model

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:

        if not results:
            return []

        return await asyncio.to_thread(self._rerank_sync, query, results, top_k)

    def _rerank_sync(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:

        model = self._get_model()

        pairs = [(query, result.chunk.content) for result in results]

        scores = model.predict(pairs)

        ranked = sorted(
            zip(scores, results),
            key=lambda pair: pair[0],
            reverse=True,
        )

        return [
            SearchResult(chunk=result.chunk, score=float(score))
            for score, result in ranked[:top_k]
        ]
