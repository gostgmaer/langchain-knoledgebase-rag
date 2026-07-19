from __future__ import annotations

from packages.knowledge.retrievers.base import BaseRetriever
from packages.knowledge.retrievers.schemas import IngestionRequest
from packages.knowledge.vectorstores.manager import VectorStoreManager
from packages.knowledge.vectorstores.schema import SearchResult


class SimilarityRetriever(BaseRetriever):

    def __init__(
        self,
        vector_store: VectorStoreManager,
    ) -> None:
        self.vector_store = vector_store

    async def retrieve(
        self,
        request: IngestionRequest,
    ) -> list[SearchResult]:

        return await self.vector_store.similarity_search(
            query_embedding=request.query_embedding,
            filters=request.filters,
            options=request.options,
        )