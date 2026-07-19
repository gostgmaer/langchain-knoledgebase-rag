# factory.py
from __future__ import annotations

from packages.config.loader import settings

from packages.knowledge.retrievers.base import BaseRetriever
from packages.knowledge.retrievers.providers.hybrid import HybridRetriever
from packages.knowledge.retrievers.providers.mmr import MMRRetriever
from packages.knowledge.retrievers.providers.similarity import (
    SimilarityRetriever,
)
from packages.knowledge.vectorstores.manager import VectorStoreManager


class RetrieverFactory:

    @staticmethod
    def create(
        vector_store: VectorStoreManager,
    ) -> BaseRetriever:

        strategy = settings.retrieval_strategy.lower()

        if strategy == "similarity":
            return SimilarityRetriever(vector_store)

        if strategy == "mmr":
            return MMRRetriever(vector_store)

        if strategy == "hybrid":
            return HybridRetriever(vector_store)

        raise ValueError(
            f"Unknown retrieval strategy: {strategy}"
        )