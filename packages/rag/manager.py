"""
RAG manager.
"""

from __future__ import annotations

from packages.application.services.chat_service import ChatService
from packages.knowledge.schemas import SearchResult
from packages.rag.builders.citation import CitationBuilder
from packages.rag.builders.context import ContextBuilder
from packages.rag.builders.prompt import PromptBuilder
from packages.rag.pipelines.retrieval import RetrievalPipeline
from packages.rag.schemas import Citation
from packages.rag.schemas import Context
from packages.rag.schemas import RAGRequest
from packages.rag.schemas import RAGResponse


class RAGManager:
    """
    Public facade for Retrieval-Augmented Generation.
    """

    def __init__(
        self,
        retrieval_pipeline: RetrievalPipeline,
        context_builder: ContextBuilder,
        prompt_builder: PromptBuilder,
        citation_builder: CitationBuilder,
        chat_service: ChatService,
    ) -> None:
        self._retrieval_pipeline = retrieval_pipeline
        self._context_builder = context_builder
        self._prompt_builder = prompt_builder
        self._citation_builder = citation_builder
        self._chat_service = chat_service

    async def retrieve(
        self,
        request: RAGRequest,
    ) -> list[SearchResult]:
        """
        Retrieve relevant search results.
        """

        return await self._retrieval_pipeline.retrieve(
            request,
        )

    def build_context(
        self,
        search_results: list[SearchResult],
    ) -> Context:
        """
        Build LLM context from search results.
        """

        return self._context_builder.build(
            search_results,
        )

    def build_prompt(
        self,
        request: RAGRequest,
        context: Context,
    ) -> str:
        """
        Build the final prompt.
        """

        return self._prompt_builder.build(
            request,
            context,
        )

    def build_citations(
        self,
        search_results: list[SearchResult],
    ) -> list[Citation]:
        """
        Build citations.
        """

        return self._citation_builder.build(
            search_results,
        )

    async def answer(
        self,
        request: RAGRequest,
    ) -> RAGResponse:
        """
        Convenience API for non-graph callers.
        """

        search_results = await self.retrieve(
            request,
        )

        context = self.build_context(
            search_results,
        )

        prompt = self.build_prompt(
            request,
            context,
        )

        response = await self._chat_service.chat(
            prompt,
        )

        citations = self.build_citations(
            search_results,
        )

        return RAGResponse(
            answer=response,
            context=context,
            citations=citations,
        )