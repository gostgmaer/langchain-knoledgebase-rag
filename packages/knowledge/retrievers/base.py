from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from packages.knowledge.retrievers.schemas import IngestionRequest
from packages.knowledge.vectorstores.schema import SearchResult


class BaseRetriever(ABC):

    @abstractmethod
    async def retrieve(
        self,
        request: IngestionRequest,
    ) -> list[SearchResult]:
        """
        Retrieve relevant chunks.
        """