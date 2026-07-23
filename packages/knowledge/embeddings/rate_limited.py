"""
Wraps a real LangChain Embeddings client so every outgoing call goes
through an EmbeddingRateLimiter first — see rate_limiter.py for why.
"""

from __future__ import annotations

from langchain_core.embeddings import Embeddings

from .rate_limiter import EmbeddingRateLimiter


class RateLimitedEmbeddings(Embeddings):
    """Async-only proxy — this app never calls the sync embed methods."""

    def __init__(self, wrapped: Embeddings, limiter: EmbeddingRateLimiter) -> None:
        self._wrapped = wrapped
        self._limiter = limiter

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Synchronous embedding is not used in this app — call aembed_documents.")

    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError("Synchronous embedding is not used in this app — call aembed_query.")

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        await self._limiter.acquire(EmbeddingRateLimiter.count_tokens(texts))
        return await self._wrapped.aembed_documents(texts)

    async def aembed_query(self, text: str) -> list[float]:
        await self._limiter.acquire(EmbeddingRateLimiter.count_tokens([text]))
        return await self._wrapped.aembed_query(text)
