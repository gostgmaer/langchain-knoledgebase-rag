# hybrid.py
from __future__ import annotations

from packages.knowledge.retrievers.base import BaseRetriever
from packages.knowledge.retrievers.schemas import RetrievalRequest


class HybridRetriever(BaseRetriever):

    async def retrieve(
        self,
        request: RetrievalRequest,
    ):
        raise NotImplementedError(
            "Hybrid retrieval is not implemented."
        )