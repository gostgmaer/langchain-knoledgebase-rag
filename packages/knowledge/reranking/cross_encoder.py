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
            zip(scores, results, strict=True),
            key=lambda pair: pair[0],
            reverse=True,
        )

        return [
            SearchResult(chunk=result.chunk, score=float(score))
            for score, result in ranked[:top_k]
        ]


def apply_relevance_floor(
    reranked: list[SearchResult],
    min_score: float,
) -> list[SearchResult]:
    """
    Drops reranked candidates scoring below `min_score` — except the
    single best-ranked one, which is always kept when the pool is
    non-empty.

    Why not filter every candidate uniformly (the original
    implementation): this cross-encoder's raw logits are unbounded and
    don't reliably separate "irrelevant" from "relevant but
    vaguely/pronoun-phrased" — empirically confirmed live, e.g. a real
    follow-up like "is it safe?" scored -8.25 against its genuinely
    correct chunk, in the same band as clearly off-topic pairs (-8 to
    -11). A uniform floor at the default 0.0 can therefore silently
    empty `citations`/`context` on a turn where retrieval genuinely
    found the right answer, simply because this specific model scored
    a vague query harshly — the exact, previously-unreproduced "correct
    answer, empty citations" bug (docs/BUILD_STATUS.md), now root-
    caused: it fires whenever query rewriting doesn't produce a
    specific standalone query (analyzer failure, or an inherently vague
    follow-up) for a retrieval-routed turn.

    Always keeping the top-1 result trades away one narrower case (a
    single, confidently *irrelevant* best-of-a-bad-pool match still
    surfaces as a low-score citation) for a strictly worse one this
    trade avoids (a real, correct citation vanishing with no trace) —
    the roadmap's own Phase 9 acceptance bar treats answers that can't
    be traced back to a source as the harder failure. The floor still
    prunes weaker stragglers ranked below the top result, which is
    where it was actually protecting against noise in a larger
    candidate pool.
    """

    if not reranked:
        return []

    return reranked[:1] + [
        result for result in reranked[1:] if result.score >= min_score
    ]
