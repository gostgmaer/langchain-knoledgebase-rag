from __future__ import annotations

import hashlib
import mimetypes
import uuid
from datetime import UTC, datetime
from uuid import UUID, uuid4

import tiktoken
from langchain_core.documents import Document as LangChainDocument
from langchain_core.messages import HumanMessage

from packages.config.loader import settings
from packages.domain.enums.document_status import DocumentStatus
from packages.domain.models.document import Document
from packages.domain.models.document_chunk import DocumentChunk
from packages.domain.models.document_version import DocumentVersion
from packages.domain.models.embedding import Embedding
from packages.infrastructure.ai.manager import LLMManager
from packages.infrastructure.repositories.document import DocumentRepository
from packages.infrastructure.repositories.document_version import DocumentVersionRepository
from packages.infrastructure.repositories.model_profile import ModelProfileRepository
from packages.knowledge.embeddings.manager import EmbeddingManager
from packages.knowledge.loaders.manager import DocumentLoaderManager
from packages.knowledge.processors.base import DocumentProcessor
from packages.knowledge.schemas import IngestionRequest, IngestionResponse
from packages.knowledge.splitters.factory import SplitterFactory
from packages.knowledge.vectorstores.manager import VectorStoreManager
from packages.sdk.upload.client import UploadClient
from packages.shared.logging import get_logger
from packages.shared.messages import normalize_message_content

_TOKENIZER = tiktoken.get_encoding("cl100k_base")

logger = get_logger(__name__)

# Bounds the ingestion-time summary prompt to a reasonable excerpt
# instead of the full document — Multi Vector Retriever's v1 scope
# (docs/mvpRAG.md v2.0) is one extra representation per *document*,
# not per chunk, specifically to keep ingestion cost bounded; an
# unbounded prompt would undercut that.
_SUMMARY_SOURCE_CHAR_LIMIT = 8000


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
        document_version_repository: DocumentVersionRepository,
        model_profile_repository: ModelProfileRepository,
        upload_client: UploadClient,
        llm: LLMManager,
    ) -> None:
        self.loader = loader
        self.transformer = transformer
        self.splitter_factory = splitter_factory
        self.embedding_manager = embedding_manager
        self.vector_store = vector_store
        self.document_repository = document_repository
        self.document_version_repository = document_version_repository
        self.model_profile_repository = model_profile_repository
        self.upload_client = upload_client
        self.llm = llm

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

        # Looked up *before* creating the new row — once the new
        # Document exists it also defaults `is_current=True` and
        # shares the same file_name, so this lookup has to happen
        # first or it can no longer tell old from new.
        previous = await self.document_repository.get_current_by_tenant_kb_and_filename(
            request.tenant_id,
            request.knowledge_base_id,
            request.document_name,
        )

        document = await self._create_document_row(
            request,
            checksum,
        )

        if previous is not None:
            await self._track_version(previous, document)

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

            await self._store_summary_representation(
                chunked_documents,
                request,
                document.id,
            )

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
    ) -> IngestionResponse:
        """
        Re-embeds an already-ingested document in place: re-downloads
        the original bytes from the Upload Service (the durable copy
        — the local scratch file from the original upload is long
        gone by the time this runs, deleted right after ingestion
        finished, see packages/api/routers/documents.py), deletes its
        old chunks, and re-runs load->clean->split->embed->store
        reusing the SAME document_id. Deliberately does NOT reuse
        ingest()'s checksum-dedup/version-tracking logic — that's for
        detecting a *new* upload of *changed* content; re-indexing an
        existing document with (deliberately) the same content isn't
        either of those.

        Re-embeds under the *current* default ModelProfile, not
        whatever profile the document originally used — Document
        itself doesn't store which profile embedded it (only
        Embedding rows do, keyed by chunk), and re-picking up the
        current default is the actual point of scheduled re-indexing:
        catching up documents after an embedding model change.
        """

        document = await self.document_repository.get(document_id)
        if document is None:
            raise ValueError(f"Cannot reindex: no document with id {document_id}")

        profile = await self.model_profile_repository.get_default()
        if profile is None:
            raise ValueError("Cannot reindex: no default model profile configured")

        settings.storage.temp_directory.mkdir(parents=True, exist_ok=True)
        scratch_path = (
            settings.storage.temp_directory
            / f"reindex_{document.id}{document.extension}"
        )

        try:
            content = await self.upload_client.files.download(
                document.file_id,
                tenant_id=str(document.tenant_id),
            )
            scratch_path.write_bytes(content)

            request = IngestionRequest(
                tenant_id=document.tenant_id,
                model_profile_id=profile.id,
                knowledge_base_id=document.knowledge_base_id,
                file=scratch_path,
                file_id=document.file_id,
                document_name=document.file_name,
            )

            await self.vector_store.store.delete_document(
                tenant_id=document.tenant_id,
                document_id=document.id,
            )

            loaded_documents = await self._load(request)
            cleaned_documents = await self._clean(loaded_documents)
            chunked_documents = await self._split(cleaned_documents, request)
            embeddings = await self._embed(chunked_documents, request, document.id)

            await self.vector_store.store.add_many(embeddings)

            document.checksum = self._checksum(scratch_path)
            document.status = DocumentStatus.READY
            await self.document_repository.session.flush()

        except Exception:
            document.status = DocumentStatus.FAILED
            await self.document_repository.session.flush()
            raise

        finally:
            scratch_path.unlink(missing_ok=True)

        return IngestionResponse(
            document_id=document.id,
            chunk_count=len(chunked_documents),
            embedding_count=len(embeddings),
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

    async def _track_version(
        self,
        previous: Document,
        new: Document,
    ) -> None:
        """
        Records that `new` supersedes `previous` — same tenant/
        knowledge-base/filename, different (already-confirmed-not-a-
        checksum-match) content. `previous` is never deleted, just
        flipped to `is_current=False`; a DocumentVersion row is
        created for it too if this is the first time it's ever been
        superseded (it won't have one yet on a document's second
        upload).
        """

        previous.is_current = False
        await self.document_repository.update(previous)

        previous_version = await self.document_version_repository.get_by_document(
            previous.id,
        )

        if previous_version is not None:
            root_document_id = previous_version.root_document_id
        else:
            root_document_id = previous.id
            await self.document_version_repository.create(
                DocumentVersion(
                    document_id=previous.id,
                    root_document_id=root_document_id,
                    version_number=1,
                    superseded_at=datetime.now(UTC),
                )
            )

        next_version_number = (
            await self.document_version_repository.max_version_number(root_document_id)
            + 1
        )

        await self.document_version_repository.create(
            DocumentVersion(
                document_id=new.id,
                root_document_id=root_document_id,
                version_number=next_version_number,
                superseded_at=None,
            )
        )

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

    async def _store_summary_representation(
        self,
        chunked_documents: list[LangChainDocument],
        request: IngestionRequest,
        document_id: UUID,
    ) -> None:
        """
        Multi Vector Retriever, v1 scope (docs/mvpRAG.md v2.0): one
        extra representation per *document* (a summary), not per-chunk
        Q&A pairs — a deliberate scope cut bounding ingestion-time LLM
        cost to one extra call per document instead of scaling with
        chunk count.

        Stored as a synthetic Chroma entry (a real `Embedding`/
        `DocumentChunk` pair, same as any other chunk) tagged
        `representation_type="summary"` — a query matching the
        *summary's* phrasing rather than any single chunk's literal
        wording can still surface this document; the retrieval side
        (MultiVectorRetriever, packages/knowledge/retrievers/providers/
        multi_vector.py) resolves a summary hit back to the document's
        real top-scoring primary chunk(s) before it ever reaches the
        LLM/citations — the summary text itself is never returned as
        literal context.

        Deliberately non-fatal: a failed summary call degrades to "no
        summary representation for this document" rather than failing
        the whole ingestion, since the primary chunks (the actually
        load-bearing search path) are already safely stored by the
        time this runs.
        """

        if not chunked_documents:
            return

        try:
            summary_text = await self._generate_summary(chunked_documents)

            if not summary_text.strip():
                return

            vector = await self.embedding_manager.client.aembed_query(summary_text)

            summary_chunk = DocumentChunk(
                id=uuid.uuid5(document_id, "summary"),
                tenant_id=request.tenant_id,
                document_id=document_id,
                chunk_index=-1,
                content=summary_text,
                token_count=len(_TOKENIZER.encode(summary_text)),
                character_count=len(summary_text),
                metadata_={},
            )

            await self.vector_store.store.add(
                Embedding(
                    tenant_id=request.tenant_id,
                    chunk_id=summary_chunk.id,
                    model_profile_id=request.model_profile_id,
                    vector=vector,
                    chunk=summary_chunk,
                ),
                representation_type="summary",
            )

        except Exception as exc:
            logger.warning(
                "Could not generate/store document summary representation",
                document_id=str(document_id),
                error=str(exc),
            )

    async def _generate_summary(
        self,
        chunked_documents: list[LangChainDocument],
    ) -> str:

        excerpt = ""
        for chunk in chunked_documents:
            if len(excerpt) >= _SUMMARY_SOURCE_CHAR_LIMIT:
                break
            excerpt += chunk.page_content + "\n\n"
        excerpt = excerpt[:_SUMMARY_SOURCE_CHAR_LIMIT]

        response = await self.llm.ainvoke(
            [
                HumanMessage(
                    content=(
                        "Summarize the following document excerpt in 2-4 sentences, "
                        "capturing its main topic and key points. Return only the "
                        "summary, no preamble.\n\n"
                        f"{excerpt}"
                    )
                )
            ]
        )

        # Gemini (and some other providers) return AIMessage.content as
        # a list of content blocks, not a plain string — the same
        # normalization LLMNode already applies to a chat response
        # (packages/graph/nodes/llm.py), reused here rather than
        # re-implemented, since a naive str(content) would literally
        # stringify the raw block list into the summary text.
        return normalize_message_content(response.content)
