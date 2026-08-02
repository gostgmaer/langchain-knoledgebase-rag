from __future__ import annotations

from abc import ABC, abstractmethod

from packages.knowledge.retrievers.schemas import RetrievalRequest
from packages.knowledge.vectorstores.schema import SearchResult


class BaseRetriever(ABC):

    @abstractmethod
    async def retrieve(
        self,
        request: RetrievalRequest,
    ) -> list[SearchResult]:
        """
        Retrieve relevant chunks.
        """