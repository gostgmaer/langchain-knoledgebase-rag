# hybrid.py
from __future__ import annotations

from packages.knowledge.retrievers.base import BaseRetriever
from packages.knowledge.retrievers.schemas import RetrievalRequest


class HybridRetriever(BaseRetriever):

    def __init__(self, vector_store) -> None:
        self.vector_store = vector_store

    async def retrieve(
        self,
        request: RetrievalRequest,
    ):
        raise NotImplementedError(
            "Hybrid retrieval is not implemented."
        )