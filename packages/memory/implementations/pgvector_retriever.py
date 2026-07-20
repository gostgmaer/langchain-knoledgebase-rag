"""
packages/memory/implementations/pgvector_retriever.py
"""

from __future__ import annotations

from packages.domain.models.memory import Memory as MemoryRow
from packages.infrastructure.repositories.memory import MemoryRepository
from packages.memory.retrieval import MemoryRetriever
from packages.memory.schemas import (
    MemoryFact,
    SearchMemoryRequest,
    SearchMemoryResponse,
    SearchResult,
)
from packages.rag.embeddings import EmbeddingManager


class PgVectorMemoryRetriever(MemoryRetriever):
    """
    Retrieves long-term memories from the dedicated `memories` table
    via pgvector cosine-similarity search — the same table
    PostgresMemoryStore writes to.
    """

    def __init__(
        self,
        repository: MemoryRepository,
        embeddings: EmbeddingManager,
    ) -> None:
        self._repository = repository
        self._embeddings = embeddings

    @staticmethod
    def _to_fact(row: MemoryRow) -> MemoryFact:
        return MemoryFact(
            id=row.id,
            tenant_id=row.tenant_id,
            user_id=row.user_id,
            conversation_id=row.conversation_id,
            type=row.type,
            content=row.content,
            importance=row.importance,
            metadata=row.metadata_,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def search(
        self,
        request: SearchMemoryRequest,
    ) -> SearchMemoryResponse:

        query_vector = await self._embeddings.client.aembed_query(
            request.query,
        )

        rows = await self._repository.search_similar(
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            query_vector=query_vector,
            k=request.top_k,
        )

        results = [
            SearchResult(memory=self._to_fact(row), score=1.0)
            for row in rows
        ]

        return SearchMemoryResponse(
            results=results,
            total=len(results),
        )
