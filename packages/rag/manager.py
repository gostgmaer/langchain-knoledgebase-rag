"""
RAG manager.
"""

from __future__ import annotations

from packages.ai.chat.service import ChatService
from packages.rag.builders.citation import CitationBuilder
from packages.rag.builders.context import ContextBuilder
from packages.rag.builders.prompt import PromptBuilder
from packages.rag.pipelines.retrieval import RetrievalPipeline
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

    async def answer(
        self,
        request: RAGRequest,
    ) -> RAGResponse:
        """
        Generate an answer using Retrieval-Augmented Generation.
        """

        search_results = await self._retrieval_pipeline.retrieve(
            request,
        )

        context = self._context_builder.build(
            search_results,
        )

        prompt = self._prompt_builder.build(
            request,
            context,
        )

        answer = await self._chat_service.chat(
            prompt,
        )

        citations = self._citation_builder.build(
            search_results,
        )

        return RAGResponse(
            answer=answer,
            context=context,
            citations=citations,
        )