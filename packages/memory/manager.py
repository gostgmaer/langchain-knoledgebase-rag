"""
packages/memory/manager.py

AI Memory Manager

Coordinates the AI Memory subsystem.

Responsibilities
----------------
- Create memory
- Update memory
- Delete memory
- Search memories
- Extract memories from conversations
- Summarize conversations

This class does NOT know anything about:
- PostgreSQL
- pgvector
- Embeddings
- LangGraph
- Checkpoints
"""

from __future__ import annotations

from uuid import UUID

from langchain_core.messages import BaseMessage

from packages.memory.extractor import MemoryExtractor
from packages.memory.retrieval import MemoryRetriever
from packages.memory.schemas import (
    CreateMemoryRequest,
    MemoryFact,
    MemoryType,
    SearchMemoryRequest,
    SearchMemoryResponse,
    UpdateMemoryRequest,
)
from packages.memory.store import MemoryStore
from packages.memory.summarizer import MemorySummarizer


class MemoryManager:
    """
    Orchestrates the AI Memory subsystem.
    """

    def __init__(
        self,
        store: MemoryStore,
        extractor: MemoryExtractor,
        summarizer: MemorySummarizer,
        retriever: MemoryRetriever,
    ) -> None:
        self._store = store
        self._extractor = extractor
        self._summarizer = summarizer
        self._retriever = retriever

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create(
        self,
        request: CreateMemoryRequest,
    ) -> MemoryFact:
        return await self._store.create(request)

    async def update(
        self,
        memory_id: UUID,
        request: UpdateMemoryRequest,
    ) -> MemoryFact:
        return await self._store.update(
            memory_id=memory_id,
            request=request,
        )

    async def delete(
        self,
        memory_id: UUID,
    ) -> None:
        await self._store.delete(memory_id)

    async def clear(
        self,
        conversation_id: UUID,
    ) -> None:
        await self._store.clear(conversation_id)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def search(
        self,
        request: SearchMemoryRequest,
    ) -> SearchMemoryResponse:
        return await self._retriever.search(request)

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    async def extract(
        self,
        *,
        conversation_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        messages: list[BaseMessage],
    ) -> list[MemoryFact]:
        memories = await self._extractor.extract(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            user_id=user_id,
            messages=messages,
        )

        if not memories:
            return []

        requests = [
            self._to_create_request(memory)
            for memory in memories
        ]

        await self._store.create_many(requests)

        return memories

    # ------------------------------------------------------------------
    # Summarization
    # ------------------------------------------------------------------

    async def summarize(
        self,
        *,
        conversation_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        messages: list[BaseMessage],
    ) -> MemoryFact:
        summary = await self._summarizer.summarize(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            user_id=user_id,
            messages=messages,
        )

        existing = await self._store.get_by_conversation_and_type(
            conversation_id,
            MemoryType.SUMMARY,
        )

        if existing is not None:
            await self._store.update(
                existing.id,
                UpdateMemoryRequest(content=summary.content),
            )
        else:
            await self._store.create(
                self._to_create_request(summary)
            )

        return summary

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_create_request(
        memory: MemoryFact,
    ) -> CreateMemoryRequest:
        return CreateMemoryRequest(
            type=memory.type,
            content=memory.content,
            tenant_id=memory.tenant_id,
            user_id=memory.user_id,
            conversation_id=memory.conversation_id,
            importance=memory.importance,
            metadata=memory.metadata,
        )