from __future__ import annotations

from uuid import UUID

from packages.knowledge.embeddings.manager import EmbeddingManager
from packages.knowledge.retrievers.manager import RetrieverManager
from packages.knowledge.retrievers.schemas import RetrievalRequest
from packages.knowledge.vectorstores.schema import (
    SearchFilter,
    SearchOptions,
    SearchResult,
)


class KnowledgeManager:
    """
    Public facade for the knowledge subsystem's read path (search only).

    Used to also wrap `IngestionPipeline` (ingest/delete/reindex/exists/count) — removed
    (docs/BUGS.md item 69) once a full-codebase check showed every real external caller already
    reached `IngestionPipeline` directly via `container.rag.ingestion_pipeline()` (reindex.py,
    connectors/sync.py, worker/jobs.py, and documents.py's own upload path), not through this
    facade; `delete_document` was the one exception, now switched to the same direct pattern
    (packages/api/routers/documents.py). `IngestionPipeline` stays genuinely request-session-bound
    on purpose (packages/infrastructure/container/rag.py's own long-standing comment on why) — this
    class dropping its forced dependency on it is what makes *this* class, the one the graph's
    `retrieve`/`tool`/`researcher` nodes depend on for search, safe to wire as a process-wide
    Singleton instead of a per-request Factory.
    """

    def __init__(
        self,
        embedding_manager: EmbeddingManager,
        retriever_manager: RetrieverManager,
    ) -> None:
        self.embedding_manager = embedding_manager
        self.retriever_manager = retriever_manager

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

