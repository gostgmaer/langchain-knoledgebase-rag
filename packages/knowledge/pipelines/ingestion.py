from __future__ import annotations

from uuid import UUID, uuid4

from langchain_core.documents import Document as LangChainDocument

from packages.domain.models.document_chunk import DocumentChunk
from packages.domain.models.embedding import Embedding

from packages.knowledge.embeddings.manager import EmbeddingManager
from packages.knowledge.loaders.manager import DocumentLoaderManager
from packages.knowledge.processors.base import DocumentProcessor
from packages.knowledge.schemas import IngestionRequest, IngestionResponse
from packages.knowledge.splitters.base import BaseSplitter
from packages.knowledge.vectorstores.manager import VectorStoreManager


class IngestionPipeline:
    """
    Handles the complete document ingestion workflow: load, clean,
    split, embed, and store into the configured vector store.

    Note: this stores chunks/embeddings in the vector store only. It
    does not yet persist a durable `documents`/`document_chunks` row
    in Postgres — that requires a KnowledgeBase + File subsystem that
    doesn't exist yet (see docs/BUILD_STATUS.md Phase 8).
    """

    def __init__(
        self,
        loader: DocumentLoaderManager,
        transformer: DocumentProcessor,
        splitter: BaseSplitter,
        embedding_manager: EmbeddingManager,
        vector_store: VectorStoreManager,
    ) -> None:
        self.loader = loader
        self.transformer = transformer
        self.splitter = splitter
        self.embedding_manager = embedding_manager
        self.vector_store = vector_store

    # ============================================================
    # Public
    # ============================================================

    async def ingest(
        self,
        request: IngestionRequest,
    ) -> IngestionResponse:

        loaded_documents = await self._load(request)

        cleaned_documents = await self._clean(loaded_documents)

        chunked_documents = await self._split(cleaned_documents)

        document_id = uuid4()

        embeddings = await self._embed(
            chunked_documents,
            request,
            document_id,
        )

        await self.vector_store.store.add_many(embeddings)

        return IngestionResponse(
            document_id=document_id,
            chunk_count=len(chunked_documents),
            embedding_count=len(embeddings),
        )

    async def delete_document(
        self,
        tenant_id: UUID,
        document_id: UUID,
    ) -> None:

        await self.vector_store.store.delete_document(
            tenant_id=tenant_id,
            document_id=document_id,
        )

    async def reindex_document(
        self,
        document_id: UUID,
    ):
        raise NotImplementedError(
            "Reindex implementation will be added later."
        )

    async def exists(
        self,
        document_id: UUID,
    ) -> bool:
        raise NotImplementedError(
            "Existence check by document_id requires durable document "
            "storage, not yet implemented."
        )

    async def count(
        self,
        tenant_id: UUID,
    ) -> int:
        return await self.vector_store.count(tenant_id)

    # ============================================================
    # Private
    # ============================================================

    async def _load(
        self,
        request: IngestionRequest,
    ) -> list[LangChainDocument]:
        return await self.loader.load(request.file)

    async def _clean(
        self,
        documents: list[LangChainDocument],
    ) -> list[LangChainDocument]:
        return await self.transformer.process(documents)

    async def _split(
        self,
        documents: list[LangChainDocument],
    ) -> list[LangChainDocument]:
        return await self.splitter.split(documents)

    async def _embed(
        self,
        documents: list[LangChainDocument],
        request: IngestionRequest,
        document_id: UUID,
    ) -> list[Embedding]:

        embeddings: list[Embedding] = []

        for index, document in enumerate(documents):

            vector = await self.embedding_manager.embed_query(
                document.page_content,
            )

            chunk = DocumentChunk(
                id=uuid4(),
                tenant_id=request.tenant_id,
                document_id=document_id,
                chunk_index=index,
                content=document.page_content,
                token_count=0,
                character_count=len(document.page_content),
                metadata_=document.metadata,
            )

            embeddings.append(
                Embedding(
                    tenant_id=request.tenant_id,
                    chunk_id=chunk.id,
                    model_profile_id=request.model_profile_id,
                    vector=vector,
                    chunk=chunk,
                )
            )

        return embeddings
