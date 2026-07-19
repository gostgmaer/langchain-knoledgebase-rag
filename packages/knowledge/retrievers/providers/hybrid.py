# hybrid.py
from __future__ import annotations

from packages.knowledge.retrievers.base import BaseRetriever
from packages.knowledge.retrievers.schemas import IngestionRequest


class HybridRetriever(BaseRetriever):

    async def retrieve(
        self,
        request: IngestionRequest,
    ):
        raise NotImplementedError(
            "Hybrid retrieval is not implemented."
        )