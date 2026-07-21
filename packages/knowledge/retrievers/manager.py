# manager.py
from __future__ import annotations

from packages.knowledge.retrievers.base import BaseRetriever
from packages.knowledge.retrievers.schemas import RetrievalRequest
from packages.knowledge.vectorstores.schema import SearchResult


class RetrieverManager:

    def __init__(
        self,
        retriever: BaseRetriever,
    ) -> None:
        self.retriever = retriever

    async def retrieve(
        self,
        request: RetrievalRequest,
    ) -> list[SearchResult]:

        return await self.retriever.retrieve(request)