# manager.py
"""
Embedding manager.
"""

from __future__ import annotations

from langchain_core.embeddings import Embeddings

from packages.knowledge.schema.chunk import KnowledgeChunk
from packages.shared.logging import get_logger

from .factory import EmbeddingFactory
from .pipeline import EmbeddingPipeline

logger = get_logger(__name__)


class EmbeddingManager:
    """
    High-level embedding service.
    """

    def __init__(self) -> None:

        self._provider = EmbeddingFactory.create()

        self._pipeline = EmbeddingPipeline(
            provider=self._provider,
        )

    @property
    def client(self) -> Embeddings:
        """The real, underlying LangChain Embeddings client."""
        return self._provider.client

    async def embed(
        self,
        chunks: list[KnowledgeChunk],
    ) -> list[KnowledgeChunk]:

        logger.info(
            "Embedding %d chunks",
            len(chunks),
        )

        return await self._pipeline.run(chunks)

    async def embed_query(
        self,
        text: str,
    ) -> list[float]:
        """Embed a single ad-hoc query, used at search time."""

        return await self._provider.embed_query(text)