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

logger = get_logger(__name__)


class GoogleEmbeddingProvider(EmbeddingProvider):

    def __init__(self) -> None:

        self._client = GoogleGenerativeAIEmbeddings(
            model=settings.rag.embedding_model,
            google_api_key=settings.ai.google_api_key,
        )

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