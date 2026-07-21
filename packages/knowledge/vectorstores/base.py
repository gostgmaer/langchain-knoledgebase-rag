from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from uuid import UUID

from packages.domain.models.embedding import Embedding
from packages.knowledge.vectorstores.schema import SearchFilter
from packages.knowledge.vectorstores.schema import SearchOptions
from packages.knowledge.vectorstores.schema import SearchResult


class BaseVectorStore(ABC):
    """
    Base interface for vector stores.

    Implementations:
        - PostgreSQL (pgvector)
        - ChromaDB
        - Qdrant (future)
        - Pinecone (future)
        - Weaviate (future)
    """

    @abstractmethod
    async def add(
        self,
        embedding: Embedding,
    ) -> None:
        """
        Store a single embedding.
        """

    @abstractmethod
    async def add_many(
        self,
        embeddings: list[Embedding],
    ) -> None:
        """
        Store multiple embeddings.
        """

    @abstractmethod
    async def similarity_search(
        self,
        query_embedding: list[float],
        *,
        filters: SearchFilter,
        options: SearchOptions | None = None,
    ) -> list[SearchResult]:
        """
        Perform semantic similarity search.
        """

    @abstractmethod
    async def mmr_search(
        self,
        query_embedding: list[float],
        *,
        filters: SearchFilter,
        options: SearchOptions | None = None,
    ) -> list[SearchResult]:
        """
        Perform Maximum Marginal Relevance search.
        """

    @abstractmethod
    async def delete_chunk(
        self,
        tenant_id: UUID,
        chunk_id: UUID,
    ) -> int:
        """
        Delete vectors belonging to a chunk.
        """

    @abstractmethod
    async def delete_document(
        self,
        tenant_id: UUID,
        document_id: UUID,
    ) -> int:
        """
        Delete vectors belonging to a document.
        """

    @abstractmethod
    async def clear(
        self,
        tenant_id: UUID,
    ) -> int:
        """
        Delete all vectors for a tenant.
        """

    @abstractmethod
    async def count(
        self,
        tenant_id: UUID,
    ) -> int:
        """
        Return total stored vectors.
        """

    @abstractmethod
    async def exists(
        self,
        tenant_id: UUID,
        chunk_id: UUID,
    ) -> bool:
        """
        Check whether a chunk is indexed.
        """