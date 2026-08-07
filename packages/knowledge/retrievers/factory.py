# factory.py
from __future__ import annotations

from packages.config.loader import settings
from packages.infrastructure.ai.manager import LLMManager
from packages.infrastructure.repositories.entity import EntityRepository
from packages.infrastructure.repositories.relationship import RelationshipRepository
from packages.knowledge.retrievers.base import BaseRetriever
from packages.knowledge.retrievers.providers.graph_rag import GraphRAGRetriever
from packages.knowledge.retrievers.providers.hybrid import HybridRetriever
from packages.knowledge.retrievers.providers.mmr import MMRRetriever
from packages.knowledge.retrievers.providers.multi_vector import (
    MultiVectorRetriever,
)
from packages.knowledge.retrievers.providers.parent_document import (
    ParentDocumentRetriever,
)
from packages.knowledge.retrievers.providers.self_query import (
    SelfQueryRetriever,
)
from packages.knowledge.retrievers.providers.similarity import (
    SimilarityRetriever,
)
from packages.knowledge.vectorstores.manager import VectorStoreManager


class RetrieverFactory:

    @staticmethod
    def create(
        vector_store: VectorStoreManager,
        llm: LLMManager,
        entity_repository: EntityRepository,
        relationship_repository: RelationshipRepository,
    ) -> BaseRetriever:

        strategy = settings.rag.retrieval_strategy.lower()

        if strategy == "similarity":
            return SimilarityRetriever(vector_store)

        if strategy == "mmr":
            return MMRRetriever(vector_store)

        if strategy == "hybrid":
            return HybridRetriever(vector_store)

        if strategy == "self_query":
            # Composition, not a replacement search algorithm — wraps
            # this app's own default general-purpose strategy (hybrid)
            # with an LLM step that extracts real metadata filters
            # before delegating (Advanced Retrieval's Self Query
            # Retriever, docs/mvpRAG.md v2.0).
            return SelfQueryRetriever(HybridRetriever(vector_store), llm)

        if strategy == "parent_document":
            # Same composition pattern — small chunks for match
            # precision via hybrid, expanded to their full parent
            # section for answer context (docs/mvpRAG.md v2.0).
            return ParentDocumentRetriever(HybridRetriever(vector_store), vector_store)

        if strategy == "multi_vector":
            # Same composition pattern — hybrid search over both real
            # chunks and document-level summary representations,
            # resolving any summary hit back to real primary chunk
            # content before it reaches the LLM/citations
            # (docs/mvpRAG.md v2.0).
            return MultiVectorRetriever(HybridRetriever(vector_store), vector_store)

        if strategy == "graph_rag":
            # Same composition pattern — hybrid search expanded with a
            # 1-hop knowledge-graph traversal (Advanced Retrieval's
            # Graph RAG, docs/mvpRAG.md v2.0), resolving neighboring
            # entities' documents back to real chunk content.
            return GraphRAGRetriever(
                HybridRetriever(vector_store),
                vector_store,
                entity_repository,
                relationship_repository,
            )

        raise ValueError(
            f"Unknown retrieval strategy: {strategy}"
        )