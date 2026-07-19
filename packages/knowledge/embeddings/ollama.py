# ollama.py
"""
Ollama embedding provider.
"""

from __future__ import annotations

from langchain_ollama import OllamaEmbeddings

from packages.config.loader import settings
from packages.shared.logging import get_logger

from packages.knowledge.schema.chunk import KnowledgeChunk

from .base import EmbeddingProvider

logger = get_logger(__name__)


class OllamaEmbeddingProvider(EmbeddingProvider):

    def __init__(self) -> None:

        self._client = OllamaEmbeddings(
            model=settings.embedding.model,
            base_url=settings.ollama.base_url,
        )

    async def embed(
        self,
        chunks: list[KnowledgeChunk],
    ) -> list[KnowledgeChunk]:

        logger.info(
            "Generating Ollama embeddings",
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