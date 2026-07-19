# manager.py
from __future__ import annotations

from packages.knowledge.retrievers.base import BaseRetriever
from packages.knowledge.retrievers.schemas import IngestionRequest
from packages.knowledge.vectorstores.schema import SearchResult


class RetrieverManager:

    def __init__(
        self,
        retriever: BaseRetriever,
    ) -> None:
        self.retriever = retriever

    async def retrieve(
        self,
        request: IngestionRequest,
    ) -> list[SearchResult]:

        return await self.retriever.retrieve(request)