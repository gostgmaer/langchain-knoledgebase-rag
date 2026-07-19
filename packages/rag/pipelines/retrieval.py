# retrieval.py
"""
RAG retrieval pipeline.
"""

from __future__ import annotations

from packages.knowledge.manager import KnowledgeManager
from packages.knowledge.retrievers.schemas import SearchRequest
from packages.knowledge.retrievers.schemas import SearchResult
from packages.rag.schemas import RAGRequest


class RetrievalPipeline:
    """
    Executes the retrieval stage of the RAG pipeline.
    """

    def __init__(
        self,
        knowledge_manager: KnowledgeManager,
    ) -> None:
        self._knowledge_manager = knowledge_manager

    async def retrieve(
        self,
        request: RAGRequest,
    ) -> list[SearchResult]:
        """
        Retrieve relevant knowledge for a user query.
        """

        search_request = SearchRequest(
            tenant_id=request.tenant_id,
            model_profile_id=request.model_profile_id,
            query=request.query,
            metadata=request.metadata,
        )

        return await self._knowledge_manager.search(
            search_request,
        )