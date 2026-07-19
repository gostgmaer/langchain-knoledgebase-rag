# manager.py
"""
Embedding manager.
"""

from __future__ import annotations

from packages.knowledge.schemas.chunk import KnowledgeChunk
from packages.shared.logging import get_logger

from .factory import EmbeddingFactory
from .pipeline import EmbeddingPipeline

logger = get_logger(__name__)


class EmbeddingManager:
    """
    High-level embedding service.
    """

    def __init__(self) -> None:

        provider = EmbeddingFactory.create()

        self._pipeline = EmbeddingPipeline(
            provider=provider,
        )

    async def embed(
        self,
        chunks: list[KnowledgeChunk],
    ) -> list[KnowledgeChunk]:

        logger.info(
            "Embedding %d chunks",
            len(chunks),
        )

        return await self._pipeline.run(chunks)