from __future__ import annotations

from uuid import UUID

from langchain_core.documents import Document

from packages.knowledge.vectorstores.base import BaseVectorStore


class VectorStorePipeline:
    """Coordinates vector store operations."""

    def __init__(
        self,
        store: BaseVectorStore,
    ) -> None:
        self._store = store

    async def add_documents(
        self,
        tenant_id: UUID,
        documents: list[Document],
        *,
        model_profile_id: UUID,
    ) -> None:
        await self._store.add_documents(
            tenant_id=tenant_id,
            documents=documents,
            model_profile_id=model_profile_id,
        )

    async def similarity_search(
        self,
        tenant_id: UUID,
        query: str,
        *,
        model_profile_id: UUID,
        k: int = 5,
    ) -> list[Document]:
        return await self._store.similarity_search(
            tenant_id=tenant_id,
            query=query,
            model_profile_id=model_profile_id,
            k=k,
        )

    async def mmr_search(
        self,
        tenant_id: UUID,
        query: str,
        *,
        model_profile_id: UUID,
        k: int = 5,
        fetch_k: int = 20,
    ) -> list[Document]:
        return await self._store.mmr_search(
            tenant_id=tenant_id,
            query=query,
            model_profile_id=model_profile_id,
            k=k,
            fetch_k=fetch_k,
        )

    async def delete_document(
        self,
        tenant_id: UUID,
        document_id: UUID,
    ) -> None:
        await self._store.delete_document(
            tenant_id=tenant_id,
            document_id=document_id,
        )

    async def delete_chunk(
        self,
        tenant_id: UUID,
        chunk_id: UUID,
    ) -> None:
        await self._store.delete_chunk(
            tenant_id=tenant_id,
            chunk_id=chunk_id,
        )

    async def clear(
        self,
        tenant_id: UUID,
    ) -> None:
        await self._store.clear(tenant_id)

    async def count(
        self,
        tenant_id: UUID,
    ) -> int:
        return await self._store.count(tenant_id)