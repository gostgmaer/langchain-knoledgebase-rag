from __future__ import annotations

from uuid import UUID

from packages.domain.models.document import Document
from packages.domain.models.document_chunk import DocumentChunk
from packages.domain.models.embedding import Embedding

from packages.infrastructure.repositories.document import DocumentRepository
from packages.infrastructure.repositories.document_chunk import (
    DocumentChunkRepository,
)
from packages.infrastructure.repositories.embedding import (
    EmbeddingRepository,
)

from packages.knowledge.embeddings.manager import EmbeddingManager
from packages.knowledge.loaders.base import BaseDocumentLoader
from packages.knowledge.processors.base import DocumentProcessor
from packages.knowledge.schemas import IngestionRequest
from packages.knowledge.splitters.base import BaseSplitter


class IngestionPipeline:
    """
    Handles the complete document ingestion workflow.
    """

    def __init__(
        self,
        loader: BaseDocumentLoader,
        transformer: DocumentProcessor,
        splitter: BaseSplitter,
        embedding_manager: EmbeddingManager,
        document_repository: DocumentRepository,
        chunk_repository: DocumentChunkRepository,
        embedding_repository: EmbeddingRepository,
    ) -> None:
        self.loader = loader
        self.transformer = transformer
        self.splitter = splitter
        self.embedding_manager = embedding_manager

        self.document_repository = document_repository
        self.chunk_repository = chunk_repository
        self.embedding_repository = embedding_repository

    # ============================================================
    # Public
    # ============================================================

    async def ingest(
        self,
        request: IngestionRequest,
    ) -> Document:

        loaded_document = await self._load(request)

        markdown = await self._transform(
            loaded_document,
        )

        chunks = await self._split(
            markdown,
            request,
        )

        embeddings = await self._embed(
            chunks,
            request,
        )

        return await self._persist(
            request,
            chunks,
            embeddings,
        )

    async def delete_document(
        self,
        tenant_id: UUID,
        document_id: UUID,
    ) -> None:

        await self.embedding_repository.delete_by_document(
            tenant_id=tenant_id,
            document_id=document_id,
        )

        await self.chunk_repository.delete_by_document(
            document_id=document_id,
        )

        await self.document_repository.delete(
            document_id,
        )

    async def reindex_document(
        self,
        document_id: UUID,
    ) -> Document:

        document = await self.document_repository.get(
            document_id,
        )

        if document is None:
            raise ValueError("Document not found.")

        raise NotImplementedError(
            "Reindex implementation will be added later."
        )

    async def exists(
        self,
        document_id: UUID,
    ) -> bool:

        return await self.document_repository.exists(
            document_id,
        )

    async def count(
        self,
        tenant_id: UUID,
    ) -> int:

        return await self.document_repository.count_by_tenant(
            tenant_id,
        )

    # ============================================================
    # Private
    # ============================================================

    async def _load(
        self,
        request: IngestionRequest,
    ):
        return await self.loader.load(
            request.file,
        )

    async def _transform(
        self,
        loaded_document,
    ):
        return await self.transformer.transform(
            loaded_document,
        )

    async def _split(
        self,
        content: str,
        request: IngestionRequest,
    ) -> list[DocumentChunk]:

        return await self.splitter.split(
            tenant_id=request.tenant_id,
            content=content,
        )

    async def _embed(
        self,
        chunks: list[DocumentChunk],
        request: IngestionRequest,
    ) -> list[Embedding]:

        return await self.embedding_manager.embed_documents(
            chunks=chunks,
            tenant_id=request.tenant_id,
            model_profile_id=request.model_profile_id,
        )

    async def _persist(
        self,
        request: IngestionRequest,
        chunks: list[DocumentChunk],
        embeddings: list[Embedding],
    ) -> Document:

        document = await self.document_repository.create(
            tenant_id=request.tenant_id,
            name=request.document_name,
            metadata=request.metadata,
        )

        for chunk in chunks:
            chunk.document_id = document.id

        for embedding, chunk in zip(
            embeddings,
            chunks,
            strict=True,
        ):
            embedding.chunk_id = chunk.id

        await self.chunk_repository.create_many(
            chunks,
        )

        await self.embedding_repository.create_many(
            embeddings,
        )

        return document