# mmr.py
from __future__ import annotations

from packages.knowledge.retrievers.base import BaseRetriever
from packages.knowledge.retrievers.schemas import RetrievalRequest
from packages.knowledge.vectorstores.manager import VectorStoreManager
from packages.knowledge.vectorstores.schema import SearchResult


class MMRRetriever(BaseRetriever):

    def __init__(
        self,
        vector_store: VectorStoreManager,
    ) -> None:
        self.vector_store = vector_store

    async def retrieve(
        self,
        request: RetrievalRequest,
    ) -> list[SearchResult]:

        return await self.vector_store.mmr_search(
            query_embedding=request.query_embedding,
            filters=request.filters,
            options=request.options,
        )