"""
packages/memory/implementations/pgvector_retriever.py
"""

from __future__ import annotations

from packages.knowledge.vectorstores.providers.pgvector import PostgresVectorStore
from packages.memory.retrieval import MemoryRetriever
from packages.memory.schemas import (
    MemoryFact,
    SearchMemoryRequest,
    SearchMemoryResponse,
    SearchResult,
)


class PgVectorMemoryRetriever(MemoryRetriever):
    """
    Retrieves long-term memories using the application's
    PgVectorStore abstraction.
    """

    def __init__(
        self,
        vector_store: PostgresVectorStore,
    ) -> None:
        self._vector_store = vector_store

    async def search(
        self,
        request: SearchMemoryRequest,
    ) -> SearchMemoryResponse:

        documents = await self._vector_store.similarity_search(
            query=request.query,
            k=request.top_k,
            filters={
                "tenant_id": str(request.tenant_id),
                "user_id": str(request.user_id),
            },
        )

        results: list[SearchResult] = []

        for document in documents:

            metadata = document.metadata

            memory = MemoryFact(
                id=metadata["id"],
                tenant_id=metadata["tenant_id"],
                user_id=metadata["user_id"],
                conversation_id=metadata.get("conversation_id"),
                type=metadata["type"],
                content=document.page_content,
                importance=metadata.get("importance", 0.5),
                metadata=metadata,
            )

            results.append(
                SearchResult(
                    memory=memory,
                    score=metadata.get("score", 1.0),
                )
            )

        return SearchMemoryResponse(
            results=results,
            total=len(results),
        )