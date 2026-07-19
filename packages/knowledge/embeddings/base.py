"""
Embedding provider interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from packages.knowledge.schemas.chunk import KnowledgeChunk


class EmbeddingProvider(ABC):
    """Base embedding provider."""

    @abstractmethod
    async def embed(
        self,
        chunks: list[KnowledgeChunk],
    ) -> list[KnowledgeChunk]:
        """
        Generate embeddings.
        """
        raise NotImplementedError