"""
Embedding pipeline.
"""

from __future__ import annotations

from packages.knowledge.schemas.chunk import KnowledgeChunk

from .base import EmbeddingProvider


class EmbeddingPipeline:
    """
    Executes the embedding stage.
    """

    def __init__(
        self,
        provider: EmbeddingProvider,
    ) -> None:

        self._provider = provider

    async def run(
        self,
        chunks: list[KnowledgeChunk],
    ) -> list[KnowledgeChunk]:

        return await self._provider.embed(chunks)