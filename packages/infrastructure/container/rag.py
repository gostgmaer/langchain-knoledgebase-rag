# Container rag setup — builds the packages.knowledge document/RAG stack.
from __future__ import annotations

import chromadb
from dependency_injector import containers, providers

from packages.config.loader import settings as app_settings
from packages.knowledge.embeddings.manager import EmbeddingManager
from packages.knowledge.extraction.graph_extractor import GraphExtractor
from packages.knowledge.loaders.manager import DocumentLoaderManager
from packages.knowledge.manager import KnowledgeManager
from packages.knowledge.pipelines.ingestion import IngestionPipeline
from packages.knowledge.processors.cleaner import DocumentCleaner
from packages.knowledge.reranking.cross_encoder import CrossEncoderReranker
from packages.knowledge.retrievers.factory import RetrieverFactory
from packages.knowledge.retrievers.manager import RetrieverManager
from packages.knowledge.splitters.factory import SplitterFactory
from packages.knowledge.splitters.markdown import MarkdownDocumentSplitter
from packages.knowledge.splitters.recursive import RecursiveDocumentSplitter
from packages.knowledge.splitters.semantic import SemanticDocumentSplitter
from packages.knowledge.vectorstores.manager import VectorStoreManager
from packages.knowledge.vectorstores.providers.chroma import ChromaVectorStore
from packages.knowledge.vectorstores.providers.pgvector import PostgresVectorStore


def _build_chroma_client() -> chromadb.ClientAPI:
    # HttpClient when a dedicated `chroma run` server is configured — see
    # packages/config/rag.py's chroma_server_host/port docstring for why:
    # the embedded PersistentClient corrupts query results under
    # concurrent multi-process access (this app's API server and arq
    # worker are separate processes, both touching the same on-disk
    # directory). Falls back to the embedded client when unset.
    if app_settings.rag.chroma_server_host and app_settings.rag.chroma_server_port:
        return chromadb.HttpClient(
            host=app_settings.rag.chroma_server_host,
            port=app_settings.rag.chroma_server_port,
        )

    return chromadb.PersistentClient(
        path=app_settings.rag.chroma_directory,
    )


class RAGContainer(
    containers.DeclarativeContainer,
):
    """
    Wires the packages.knowledge document-processing/RAG stack: real
    loaders (PDF/TXT/MD/DOCX/HTML/JSON/CSV), real cleaning, real
    splitting (recursive/markdown/semantic), real embeddings, and a
    real Chroma-backed vector store.
    """

    settings = providers.DependenciesContainer()

    ai = providers.DependenciesContainer()

    services = providers.DependenciesContainer()

    repositories = providers.DependenciesContainer()

    upload = providers.DependenciesContainer()

    # Only `retriever` (graph_rag's entity/relationship reads — docs/BUGS.md item 69) needs this.
    database = providers.DependenciesContainer()

    platform_settings = providers.DependenciesContainer()

    embeddings = providers.Singleton(
        EmbeddingManager,
    )

    # Only actually built when settings.rag.vector_store_backend == "chroma"
    # — dependency_injector still constructs every branch's dependency
    # graph eagerly if it's a Singleton touched anywhere, but this one is
    # lazy (nothing resolves chroma_client at all on the pgvector path,
    # since vectorstore_backend below never selects it), so no chroma
    # connection is attempted unless Chroma is the configured backend.
    chroma_client = providers.Singleton(
        _build_chroma_client,
    )

    # settings.rag.vector_store_backend picks the real implementation —
    # previously a dead config field, ChromaVectorStore was hardcoded
    # regardless of its value. "pgvector" reuses the Postgres this app
    # already runs (packages/knowledge/vectorstores/providers/pgvector.py,
    # a genuinely complete BaseVectorStore implementation, not a stub) —
    # one less moving part than standing up a dedicated Chroma server.
    # Known trade-off, not hidden: settings.embedding.dimensions (3072)
    # exceeds pgvector's HNSW/IVFFlat 2000-dimension index ceiling (see
    # packages/domain/models/embedding.py's own docstring), so similarity
    # search here is an unindexed, brute-force ORDER BY — fine at small
    # scale, not for a large corpus without also revisiting the embedding
    # dimension or pgvector's index options.
    #
    # Both branches are Factory, not Singleton, deliberately: pgvector's
    # PostgresVectorStore needs a fresh per-request session
    # (repositories.session, itself Factory-wired onto a per-request
    # connection — see repositories.py) — a Singleton here would capture
    # the first request's session forever, the exact DI-lifetime bug this
    # codebase has already hit twice (memory pipeline, ingestion
    # pipeline). Chroma's client-based backend doesn't need this, but is
    # kept Factory too so switching backends is just a config change, not
    # a lifetime rule to remember.
    vectorstore_backend = providers.Selector(
        providers.Callable(lambda: app_settings.rag.vector_store_backend),
        chroma=providers.Factory(
            ChromaVectorStore,
            client=chroma_client,
            collection_name=app_settings.rag.vector_collection_name,
        ),
        pgvector=providers.Factory(
            PostgresVectorStore,
            session=repositories.session,
        ),
    )

    vectorstore = providers.Factory(
        VectorStoreManager,
        store=vectorstore_backend,
    )

    loader = providers.Singleton(
        DocumentLoaderManager,
    )

    cleaner = providers.Singleton(
        DocumentCleaner,
    )

    recursive_splitter = providers.Singleton(
        RecursiveDocumentSplitter,
    )

    markdown_splitter = providers.Singleton(
        MarkdownDocumentSplitter,
    )

    semantic_splitter = providers.Singleton(
        SemanticDocumentSplitter,
        embeddings=embeddings,
    )

    splitter_factory = providers.Singleton(
        SplitterFactory,
        recursive_splitter=recursive_splitter,
        markdown_splitter=markdown_splitter,
        semantic_splitter=semantic_splitter,
    )

    # Factory, not Singleton — cheap, stateless-per-instance LLM wrapper,
    # same shape as query_analyzer's own provider entry (graph.py).
    graph_extractor = providers.Factory(
        GraphExtractor,
        llm=ai.manager,
    )

    # Stays Factory, deliberately — genuinely needs a real per-request database session threaded
    # through document_repository/document_version_repository/model_profile_repository/
    # entity_repository/relationship_repository for one atomic ingest, not just a read. A
    # Singleton here would be constructed once, the first time anything touches it, permanently
    # capturing whatever session existed at that moment — the exact bug fixed earlier for the
    # memory pipeline (docs/TUTORIAL_LONG_TERM_MEMORY.md's "Bug 3"). Real callers all reach this
    # directly (`container.rag.ingestion_pipeline()` — documents.py, reindex.py,
    # connectors/sync.py, worker/jobs.py), not through KnowledgeManager, which dropped its
    # ingestion-facade surface entirely for exactly this reason (docs/BUGS.md item 69).

    ingestion_pipeline = providers.Factory(
        IngestionPipeline,
        loader=loader,
        transformer=cleaner,
        splitter_factory=splitter_factory,
        embedding_manager=embeddings,
        vector_store=vectorstore,
        document_repository=repositories.document,
        document_version_repository=repositories.document_version,
        model_profile_repository=repositories.model_profile,
        upload_client=upload.client,
        llm=ai.manager,
        graph_extractor=graph_extractor,
        entity_repository=repositories.entity,
        relationship_repository=repositories.relationship,
    )

    # Lazy, not eager — constructed on first real use so that the
    # cross-encoder's ~90MB model download doesn't happen at app
    # startup / dev server boot.
    reranker = providers.Singleton(
        CrossEncoderReranker,
    )

    # Singleton as of docs/BUGS.md item 69 (was Factory since Graph RAG, docs/mvpRAG.md v2.0,
    # when RetrieverFactory.create() started always taking entity/relationship repositories —
    # unused by every strategy except "graph_rag", same as `llm` is already unused by
    # similarity/mmr/hybrid). `GraphRAGRetriever` now takes a `session_factory` instead of
    # already-bound repository instances, opening its own session only for the one `retrieve()`
    # call that actually needs the graph traversal — nothing session-bound is captured at
    # construction time anymore, so this is safe to build once and reuse (the same fix already
    # applied to the memory pipeline — see that container's own comment on the identical bug
    # class, docs/TUTORIAL_LONG_TERM_MEMORY.md's "Bug 3"). This is what lets the graph's
    # `retrieve`/`tool`/`researcher` nodes stop rebuilding their search path on every request.
    retriever = providers.Singleton(
        RetrieverFactory.create,
        vector_store=vectorstore,
        llm=ai.manager,
        session_factory=database.session_factory,
        platform_settings=platform_settings.service,
    )

    retriever_manager = providers.Singleton(
        RetrieverManager,
        retriever=retriever,
    )

    # Singleton as of docs/BUGS.md item 69 — dropped its `ingestion_pipeline` dependency entirely
    # (see KnowledgeManager's own docstring), which was the only thing forcing this to Factory.
    knowledge_manager = providers.Singleton(
        KnowledgeManager,
        embedding_manager=embeddings,
        retriever_manager=retriever_manager,
    )
