from __future__ import annotations

from uuid import UUID

from packages.knowledge.embeddings.manager import EmbeddingManager
from packages.knowledge.pipelines.ingestion import IngestionPipeline
from packages.knowledge.retrievers.manager import RetrieverManager
from packages.knowledge.retrievers.schemas import RetrievalRequest
from packages.knowledge.schemas import IngestionRequest, IngestionResponse
from packages.knowledge.vectorstores.schema import (
    SearchFilter,
    SearchOptions,
    SearchResult,
)


class KnowledgeManager:
    """
    Public facade for the knowledge subsystem.
    """

    def __init__(
        self,
        ingestion_pipeline: IngestionPipeline,
        embedding_manager: EmbeddingManager,
        retriever_manager: RetrieverManager,
    ) -> None:
        self.ingestion_pipeline = ingestion_pipeline
        self.embedding_manager = embedding_manager
        self.retriever_manager = retriever_manager

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    async def ingest(
        self,
        request: IngestionRequest,
    ) -> IngestionResponse:
        return await self.ingestion_pipeline.ingest(request)

    async def ingest_many(
        self,
        requests: list[IngestionRequest],
    ) -> list[IngestionResponse]:
        responses: list[IngestionResponse] = []

        for request in requests:
            response = await self.ingestion_pipeline.ingest(request)
            responses.append(response)

        return responses

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        filters: SearchFilter,
        options: SearchOptions | None = None,
    ) -> list[SearchResult]:

        query_embedding = await self.embedding_manager.embed_query(query)

        request = RetrievalRequest(
            query_embedding=query_embedding,
            filters=filters,
            query=query,
            options=options,
        )

        return await self.retriever_manager.retrieve(request)

    async def search_by_document(
        self,
        query: str,
        tenant_id: UUID,
        model_profile_id: UUID,
        document_id: UUID,
        options: SearchOptions | None = None,
    ) -> list[SearchResult]:

        filters = SearchFilter(
            tenant_id=tenant_id,
            model_profile_id=model_profile_id,
            document_id=document_id,
        )

        return await self.search(
            query=query,
            filters=filters,
            options=options,
        )

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    async def delete_document(
        self,
        tenant_id: UUID,
        document_id: UUID,
    ) -> None:
        await self.ingestion_pipeline.delete_document(
            tenant_id=tenant_id,
            document_id=document_id,
        )

    async def reindex_document(
        self,
        document_id: UUID,
    ):
        return await self.ingestion_pipeline.reindex_document(
            document_id=document_id,
        )

    async def exists(
        self,
        document_id: UUID,
    ) -> bool:
        return await self.ingestion_pipeline.exists(
            document_id=document_id,
        )

    async def count(
        self,
        tenant_id: UUID,
    ) -> int:
        return await self.ingestion_pipeline.count(
            tenant_id=tenant_id,
        )