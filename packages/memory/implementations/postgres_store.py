"""
packages/memory/implementations/postgres_store.py
"""

from __future__ import annotations

from uuid import UUID

from packages.domain.models.memory import Memory as MemoryRow
from packages.infrastructure.repositories.memory import MemoryRepository
from packages.memory.schemas import (
    CreateMemoryRequest,
    MemoryFact,
    SearchMemoryRequest,
    SearchMemoryResponse,
    SearchResult,
    UpdateMemoryRequest,
)
from packages.memory.store import MemoryStore
from packages.rag.embeddings import EmbeddingManager


class PostgresMemoryStore(MemoryStore):
    """
    PostgreSQL + pgvector implementation of MemoryStore.
    """

    def __init__(
        self,
        repository: MemoryRepository,
        embeddings: EmbeddingManager,
    ) -> None:
        self._repository = repository
        self._embeddings = embeddings

    async def _embed(self, text: str) -> list[float]:
        return await self._embeddings.client.aembed_query(text)

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

    # ---------------------------------------------------------
    # Create
    # ---------------------------------------------------------

    async def create(
        self,
        request: CreateMemoryRequest,
    ) -> MemoryFact:

        row = MemoryRow(
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            type=request.type,
            content=request.content,
            importance=request.importance,
            vector=await self._embed(request.content),
            metadata_=request.metadata,
        )

        row = await self._repository.create(row)

        return self._to_fact(row)

    async def create_many(
        self,
        requests: list[CreateMemoryRequest],
    ) -> list[MemoryFact]:

        return [
            await self.create(request)
            for request in requests
        ]

    # ---------------------------------------------------------
    # Read
    # ---------------------------------------------------------

    async def get(
        self,
        memory_id: UUID,
    ) -> MemoryFact | None:

        row = await self._repository.get(memory_id)

        return self._to_fact(row) if row is not None else None

    # ---------------------------------------------------------
    # Update
    # ---------------------------------------------------------

    async def update(
        self,
        memory_id: UUID,
        request: UpdateMemoryRequest,
    ) -> MemoryFact:

        row = await self._repository.get(memory_id)

        if row is None:
            raise ValueError(f"Memory '{memory_id}' not found.")

        if request.content is not None:
            row.content = request.content
            row.vector = await self._embed(request.content)

        if request.importance is not None:
            row.importance = request.importance

        if request.metadata is not None:
            row.metadata_ = request.metadata

        row = await self._repository.update(row)

        return self._to_fact(row)

    # ---------------------------------------------------------
    # Delete
    # ---------------------------------------------------------

    async def delete(
        self,
        memory_id: UUID,
    ) -> None:

        await self._repository.delete_by_id(memory_id)

    async def clear(
        self,
        conversation_id: UUID,
    ) -> None:

        await self._repository.delete_by_conversation(conversation_id)

    # ---------------------------------------------------------
    # Search
    # ---------------------------------------------------------

    async def search(
        self,
        request: SearchMemoryRequest,
    ) -> SearchMemoryResponse:

        rows = await self._repository.search_similar(
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            query_vector=await self._embed(request.query),
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
