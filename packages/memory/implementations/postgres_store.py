"""
packages/memory/implementations/postgres_store.py
"""

from __future__ import annotations

from uuid import UUID, uuid4

from packages.memory.schemas import (
    CreateMemoryRequest,
    MemoryFact,
    SearchMemoryRequest,
    SearchMemoryResponse,
    UpdateMemoryRequest,
)
from packages.memory.store import MemoryStore


class PostgresMemoryStore(MemoryStore):
    """
    PostgreSQL implementation of MemoryStore.

    NOTE:
    Database access is intentionally left as TODO/placeholder.
    Replace with your SQLAlchemy/asyncpg implementation.
    """

    def __init__(
        self,
        db,
    ) -> None:
        self._db = db

    # ---------------------------------------------------------
    # Create
    # ---------------------------------------------------------

    async def create(
        self,
        request: CreateMemoryRequest,
    ) -> MemoryFact:

        memory = MemoryFact(
            id=uuid4(),
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            type=request.type,
            content=request.content,
            importance=request.importance,
            metadata=request.metadata,
        )

        # INSERT INTO memories ...

        return memory

    async def create_many(
        self,
        requests: list[CreateMemoryRequest],
    ) -> list[MemoryFact]:

        memories = [
            MemoryFact(
                id=uuid4(),
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                conversation_id=request.conversation_id,
                type=request.type,
                content=request.content,
                importance=request.importance,
                metadata=request.metadata,
            )
            for request in requests
        ]

        # Bulk INSERT

        return memories

    # ---------------------------------------------------------
    # Read
    # ---------------------------------------------------------

    async def get(
        self,
        memory_id: UUID,
    ) -> MemoryFact | None:

        # SELECT ...

        return None

    # ---------------------------------------------------------
    # Update
    # ---------------------------------------------------------

    async def update(
        self,
        memory_id: UUID,
        request: UpdateMemoryRequest,
    ) -> MemoryFact:

        # UPDATE ...

        raise NotImplementedError

    # ---------------------------------------------------------
    # Delete
    # ---------------------------------------------------------

    async def delete(
        self,
        memory_id: UUID,
    ) -> None:

        # DELETE ...

        return

    async def clear(
        self,
        conversation_id: UUID,
    ) -> None:

        # DELETE WHERE conversation_id = ...

        return

    # ---------------------------------------------------------
    # Search
    # ---------------------------------------------------------

    async def search(
        self,
        request: SearchMemoryRequest,
    ) -> SearchMemoryResponse:

        # Will later use pgvector similarity search

        return SearchMemoryResponse()
    




