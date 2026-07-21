"""
Embedding provider interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from langchain_core.embeddings import Embeddings

from packages.knowledge.schema.chunk import KnowledgeChunk


class EmbeddingProvider(ABC):
    """Base embedding provider."""

    @property
    @abstractmethod
    def client(self) -> Embeddings:
        """
        The real, underlying LangChain Embeddings client — needed
        anywhere a raw LangChain-compatible embedding function is
        required (e.g. handing to a vector store).
        """
        raise NotImplementedError

    @abstractmethod
    async def embed(
        self,
        chunks: list[KnowledgeChunk],
    ) -> list[KnowledgeChunk]:
        """
        Generate embeddings for a batch of chunks (ingestion time).
        """
        raise NotImplementedError

    @abstractmethod
    async def embed_query(
        self,
        text: str,
    ) -> list[float]:
        """
        Generate an embedding for a single ad-hoc query (search time).
        """
        raise NotImplementedError