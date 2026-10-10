"""
packages/memory/store.py

AI Memory Store Interface

Persistence contract for long-term AI memory.

Implementations may use:
- PostgreSQL + pgvector
- Redis
- Chroma
- Pinecone
- Weaviate
- Qdrant

The manager depends only on this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from packages.memory.schemas import (
    CreateMemoryRequest,
    MemoryFact,
    MemoryType,
    SearchMemoryRequest,
    SearchMemoryResponse,
    UpdateMemoryRequest,
)


class MemoryStore(ABC):
    """Persistence abstraction for AI memories."""

    @abstractmethod
    async def create(
        self,
        request: CreateMemoryRequest,
    ) -> MemoryFact:
        """
        Persist a new memory.
        """
        ...

    @abstractmethod
    async def update(
        self,
        memory_id: UUID,
        request: UpdateMemoryRequest,
    ) -> MemoryFact:
        """
        Update an existing memory.
        """
        ...

    @abstractmethod
    async def delete(
        self,
        memory_id: UUID,
    ) -> None:
        """
        Delete a memory.
        """
        ...

    @abstractmethod
    async def get(
        self,
        memory_id: UUID,
    ) -> MemoryFact | None:
        """
        Retrieve a memory by its identifier.
        """
        ...

    @abstractmethod
    async def search(
        self,
        request: SearchMemoryRequest,
    ) -> SearchMemoryResponse:
        """
        Perform semantic memory search.
        """
        ...

    @abstractmethod
    async def clear(
        self,
        conversation_id: UUID,
    ) -> None:
        """
        Remove all memories associated with a conversation.
        """
        ...

    @abstractmethod
    async def create_many(
        self,
        requests: list[CreateMemoryRequest],
    ) -> list[MemoryFact]:
        """
        Persist multiple memories in a single operation.
        """
        ...

    @abstractmethod
    async def get_by_conversation_and_type(
        self,
        conversation_id: UUID,
        type: MemoryType,
    ) -> MemoryFact | None:
        """
        Retrieve the existing memory of a given type for a conversation,
        if one exists (e.g. a conversation's running summary).
        """
        ...

    @abstractmethod
    async def upsert_summary(
        self,
        request: CreateMemoryRequest,
    ) -> MemoryFact:
        """
        Atomically creates a conversation's SUMMARY memory, or replaces its content if one already
        exists — `request.type` must be `MemoryType.SUMMARY`. Unlike a caller doing
        `get_by_conversation_and_type()` then `create()`/`update()` itself, this must never leave a
        window where two concurrent callers for the same conversation each see "none yet" and both
        create one: implementations back this with a real atomic database operation (e.g. Postgres
        `INSERT ... ON CONFLICT DO UPDATE`), not an application-level check-then-act.
        """
        ...
