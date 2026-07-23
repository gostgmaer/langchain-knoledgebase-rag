"""
Google embedding provider.
"""

from __future__ import annotations

from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from packages.config.loader import settings
from packages.shared.logging import get_logger

from packages.knowledge.schema.chunk import KnowledgeChunk

from .base import EmbeddingProvider
from .rate_limited import RateLimitedEmbeddings
from .rate_limiter import EmbeddingRateLimiter

logger = get_logger(__name__)


class GoogleEmbeddingProvider(EmbeddingProvider):

    def __init__(self) -> None:

        raw_client = GoogleGenerativeAIEmbeddings(
            model=settings.rag.embedding_model,
            google_api_key=settings.ai.google_api_key,
        )

        # Gemini's own free-tier quota (100 requests/min) is what a
        # backlog of concurrent ingestion jobs blew through in practice —
        # cap below it here so this app degrades to a bounded wait instead
        # of a 429 the moment several documents queue up at once.
        limiter = EmbeddingRateLimiter(
            max_requests=settings.rag.embedding_rate_limit_requests_per_minute,
            max_tokens=settings.rag.embedding_rate_limit_tokens_per_minute,
        )
        self._client = RateLimitedEmbeddings(wrapped=raw_client, limiter=limiter)

    @property
    def client(self) -> Embeddings:
        return self._client

    async def embed(
        self,
        chunks: list[KnowledgeChunk],
    ) -> list[KnowledgeChunk]:

        logger.info(
            "Generating Google embeddings",
            chunks=len(chunks),
        )

        vectors = await self._client.aembed_documents(
            [
                chunk.document.page_content
                for chunk in chunks
            ]
        )

        for chunk, vector in zip(
            chunks,
            vectors,
            strict=True,
        ):
            chunk.embedding = vector

        return chunks

    async def embed_query(
        self,
        text: str,
    ) -> list[float]:
        return await self._client.aembed_query(text)