from __future__ import annotations

from uuid import UUID

from packages.domain.models.embedding import Embedding
from packages.knowledge.vectorstores.base import BaseVectorStore
from packages.knowledge.vectorstores.schema import (
    SearchFilter,
    SearchOptions,
    SearchResult,
)


class VectorStoreManager:

    def __init__(
        self,
        store: BaseVectorStore,
    ) -> None:
        self.store = store

    async def similarity_search(
        self,
        query_embedding: Embedding,
        *,
        filters: SearchFilter,
        options: SearchOptions | None = None,
    ) -> list[SearchResult]:
        return await self.store.similarity_search(
            query_embedding=query_embedding,
            filters=filters,
            options=options,
        )

    async def mmr_search(
        self,
        query_embedding: Embedding,
        *,
        filters: SearchFilter,
        options: SearchOptions | None = None,
    ) -> list[SearchResult]:
        return await self.store.mmr_search(
            query_embedding=query_embedding,
            filters=filters,
            options=options,
        )

    async def count(
        self,
        tenant_id: UUID,
    ) -> int:
        return await self.store.count(
            tenant_id=tenant_id,
        )

    async def exists(
        self,
        tenant_id: UUID,
        chunk_id: UUID,
    ) -> bool:
        return await self.store.exists(
            tenant_id=tenant_id,
            chunk_id=chunk_id,
        )