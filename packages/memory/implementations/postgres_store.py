"""
packages/memory/implementations/postgres_store.py
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.domain.models.memory import Memory as MemoryRow
from packages.infrastructure.repositories.memory import MemoryRepository
from packages.knowledge.embeddings.manager import EmbeddingManager
from packages.memory.schemas import (
    CreateMemoryRequest,
    MemoryFact,
    MemoryType,
    SearchMemoryRequest,
    SearchMemoryResponse,
    SearchResult,
    UpdateMemoryRequest,
)
from packages.memory.store import MemoryStore


class PostgresMemoryStore(MemoryStore):
    """
    PostgreSQL + pgvector implementation of MemoryStore.

    Takes a raw `session_factory` rather than an already-bound `MemoryRepository` (docs/BUGS.md
    item 69) — opens its own fresh session per call instead. This is what makes the class safe to
    wire as a process-wide Singleton: the prior `repository`-at-construction-time shape is exactly
    the pattern that already caused a real, silent data-loss bug once in this app — a Singleton
    resolved before any request existed permanently captured a session nothing would ever commit
    (docs/TUTORIAL_LONG_TERM_MEMORY.md's "Bug 3"). A `session_factory` closure has nothing to
    capture; every call opens, uses, commits, and closes its own session — the same shape already
    proven safe by RetrievalLogService/PlatformSettingsService/AuditService.

    Side effect of this shape: `create_many()`'s writes (extract_memory's batch of newly-found
    facts) are no longer one all-or-nothing transaction — each fact now commits independently. A
    mid-batch failure now keeps whichever facts succeeded before it instead of losing the whole
    batch, consistent with this app's existing "one bad item shouldn't sink an entire batch"
    convention elsewhere (the scheduled reindex sweep, ingestion audit).
    """

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession] | async_sessionmaker,
        embeddings: EmbeddingManager,
    ) -> None:
        self._session_factory = session_factory
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

        async with self._session_factory() as session:
            row = await MemoryRepository(session).create(row)
            await session.commit()

        return self._to_fact(row)

    async def create_many(
        self,
        requests: list[CreateMemoryRequest],
    ) -> list[MemoryFact]:

        return [
            await self.create(request)
            for request in requests
        ]

    async def upsert_summary(
        self,
        request: CreateMemoryRequest,
    ) -> MemoryFact:

        assert request.type == MemoryType.SUMMARY, "upsert_summary is only for MemoryType.SUMMARY"

        vector = await self._embed(request.content)

        async with self._session_factory() as session:
            row = await MemoryRepository(session).upsert_summary(
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                conversation_id=request.conversation_id,
                content=request.content,
                importance=request.importance,
                vector=vector,
                metadata=request.metadata,
            )
            await session.commit()

        return self._to_fact(row)

    # ---------------------------------------------------------
    # Read
    # ---------------------------------------------------------

    async def get(
        self,
        memory_id: UUID,
    ) -> MemoryFact | None:

        async with self._session_factory() as session:
            row = await MemoryRepository(session).get(memory_id)

        return self._to_fact(row) if row is not None else None

    async def get_by_conversation_and_type(
        self,
        conversation_id: UUID,
        type: MemoryType,
    ) -> MemoryFact | None:

        async with self._session_factory() as session:
            row = await MemoryRepository(session).get_by_conversation_and_type(
                conversation_id=conversation_id,
                type=type,
            )

        return self._to_fact(row) if row is not None else None

    # ---------------------------------------------------------
    # Update
    # ---------------------------------------------------------

    async def update(
        self,
        memory_id: UUID,
        request: UpdateMemoryRequest,
    ) -> MemoryFact:

        new_vector = await self._embed(request.content) if request.content is not None else None

        async with self._session_factory() as session:
            repository = MemoryRepository(session)
            row = await repository.get(memory_id)

            if row is None:
                raise ValueError(f"Memory '{memory_id}' not found.")

            if request.content is not None:
                row.content = request.content
                row.vector = new_vector

            if request.importance is not None:
                row.importance = request.importance

            if request.metadata is not None:
                row.metadata_ = request.metadata

            row = await repository.update(row)
            await session.commit()

        return self._to_fact(row)

    # ---------------------------------------------------------
    # Delete
    # ---------------------------------------------------------

    async def delete(
        self,
        memory_id: UUID,
    ) -> None:

        async with self._session_factory() as session:
            await MemoryRepository(session).delete_by_id(memory_id)
            await session.commit()

    async def clear(
        self,
        conversation_id: UUID,
    ) -> None:

        async with self._session_factory() as session:
            await MemoryRepository(session).delete_by_conversation(conversation_id)
            await session.commit()

    # ---------------------------------------------------------
    # Search
    # ---------------------------------------------------------

    async def search(
        self,
        request: SearchMemoryRequest,
    ) -> SearchMemoryResponse:

        query_vector = await self._embed(request.query)

        async with self._session_factory() as session:
            rows = await MemoryRepository(session).search_similar(
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
