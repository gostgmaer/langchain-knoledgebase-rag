from __future__ import annotations

import hashlib
import mimetypes
from datetime import UTC, datetime
from uuid import UUID, uuid4

import tiktoken
from langchain_core.documents import Document as LangChainDocument

from packages.domain.enums.document_status import DocumentStatus
from packages.domain.models.document import Document
from packages.domain.models.document_chunk import DocumentChunk
from packages.domain.models.embedding import Embedding

from packages.infrastructure.repositories.document import DocumentRepository
from packages.knowledge.embeddings.manager import EmbeddingManager
from packages.knowledge.loaders.manager import DocumentLoaderManager
from packages.knowledge.processors.base import DocumentProcessor
from packages.knowledge.schemas import IngestionRequest, IngestionResponse
from packages.knowledge.splitters.factory import SplitterFactory
from packages.knowledge.vectorstores.manager import VectorStoreManager

_TOKENIZER = tiktoken.get_encoding("cl100k_base")


class IngestionPipeline:
    """
    Handles the complete document ingestion workflow: checksum-based
    change detection, load, clean, split, embed, and store into the
    configured vector store.

    Chunk content is the vector store's responsibility, same as
    before — the Document row created here is bookkeeping for
    identity/checksum/status only, so a repeat upload of unchanged
    content can be detected and skipped (incremental indexing)
    without restructuring the already-working search path.
    """

    def __init__(
        self,
        loader: DocumentLoaderManager,
        transformer: DocumentProcessor,
        splitter_factory: SplitterFactory,
        embedding_manager: EmbeddingManager,
        vector_store: VectorStoreManager,
        document_repository: DocumentRepository,
    ) -> None:
        self.loader = loader
        self.transformer = transformer
        self.splitter_factory = splitter_factory
        self.embedding_manager = embedding_manager
        self.vector_store = vector_store
        self.document_repository = document_repository

    # ============================================================
    # Public
    # ============================================================

    async def ingest(
        self,
        request: IngestionRequest,
    ) -> IngestionResponse:

        checksum = self._checksum(request.file)

        existing = await self.document_repository.get_by_checksum(
            request.knowledge_base_id,
            checksum,
        )
        if existing is not None:
            return IngestionResponse(
                document_id=existing.id,
                chunk_count=0,
                embedding_count=0,
                skipped=True,
            )

        document = await self._create_document_row(
            request,
            checksum,
        )

        try:
            loaded_documents = await self._load(request)

            cleaned_documents = await self._clean(loaded_documents)

            chunked_documents = await self._split(
                cleaned_documents,
                request,
            )

            embeddings = await self._embed(
                chunked_documents,
                request,
                document.id,
            )

            await self.vector_store.store.add_many(embeddings)

            document.status = DocumentStatus.READY
            await self.document_repository.session.flush()

        except Exception:
            document.status = DocumentStatus.FAILED
            await self.document_repository.session.flush()
            raise

        return IngestionResponse(
            document_id=document.id,
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
        return await self.document_repository.exists(document_id)

    async def count(
        self,
        tenant_id: UUID,
    ) -> int:
        return await self.vector_store.count(tenant_id)

    # ============================================================
    # Private
    # ============================================================

    @staticmethod
    def _checksum(path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    async def _create_document_row(
        self,
        request: IngestionRequest,
        checksum: str,
    ) -> Document:

        mime_type, _ = mimetypes.guess_type(request.file.name)

        document = Document(
            knowledge_base_id=request.knowledge_base_id,
            tenant_id=request.tenant_id,
            title=request.document_name,
            file_id=request.file_id or str(uuid4()),
            file_name=request.document_name,
            mime_type=mime_type or "application/octet-stream",
            extension=request.file.suffix.lower(),
            size_bytes=request.file.stat().st_size,
            checksum=checksum,
            status=DocumentStatus.PROCESSING,
            metadata_=request.metadata,
        )

        return await self.document_repository.create(document)

    async def _load(
        self,
        request: IngestionRequest,
    ) -> list[LangChainDocument]:
        documents = await self.loader.load(request.file)

        ingested_at = datetime.now(UTC).isoformat()
        for document in documents:
            document.metadata.setdefault("ingested_at", ingested_at)

        return documents

    async def _clean(
        self,
        documents: list[LangChainDocument],
    ) -> list[LangChainDocument]:
        return await self.transformer.process(documents)

    async def _split(
        self,
        documents: list[LangChainDocument],
        request: IngestionRequest,
    ) -> list[LangChainDocument]:
        splitter = self.splitter_factory.create(
            strategy=request.chunking_strategy,
            file_extension=request.file.suffix.lower(),
        )
        return await splitter.split(documents)

    async def _embed(
        self,
        documents: list[LangChainDocument],
        request: IngestionRequest,
        document_id: UUID,
    ) -> list[Embedding]:

        if not documents:
            return []

        vectors = await self.embedding_manager.client.aembed_documents(
            [document.page_content for document in documents]
        )

        embeddings: list[Embedding] = []

        for index, (document, vector) in enumerate(
            zip(documents, vectors, strict=True)
        ):

            page = document.metadata.get("page")

            section = (
                document.metadata.get("h1")
                or document.metadata.get("h2")
                or document.metadata.get("h3")
            )

            chunk = DocumentChunk(
                id=uuid4(),
                tenant_id=request.tenant_id,
                document_id=document_id,
                chunk_index=index,
                page_number=(page + 1) if isinstance(page, int) else None,
                section=section,
                content=document.page_content,
                token_count=len(_TOKENIZER.encode(document.page_content)),
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
