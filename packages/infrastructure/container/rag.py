# Container rag setup — builds the packages.knowledge document/RAG stack.
from __future__ import annotations

import chromadb
from dependency_injector import containers
from dependency_injector import providers

from packages.config.loader import settings as app_settings
from packages.knowledge.embeddings.manager import EmbeddingManager
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


def _build_chroma_client() -> chromadb.ClientAPI:
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

    embeddings = providers.Singleton(
        EmbeddingManager,
    )

    chroma_client = providers.Singleton(
        _build_chroma_client,
    )

    vectorstore_backend = providers.Singleton(
        ChromaVectorStore,
        client=chroma_client,
        collection_name=app_settings.rag.vector_collection_name,
    )

    vectorstore = providers.Singleton(
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

    # NOTE: ingestion_pipeline and knowledge_manager are Factory, not
    # Singleton, on purpose — ingestion_pipeline now depends on
    # repositories.document, which is itself Factory-wired onto a
    # per-request database session (see packages/infrastructure/
    # container/repositories.py + packages/api/dependencies.py's
    # request_scoped_session). A Singleton here would be constructed
    # once, the first time anything touches it, permanently capturing
    # whatever session existed at that moment — the exact bug fixed
    # earlier for the memory pipeline (see docs/CHANGELOG.md).

    ingestion_pipeline = providers.Factory(
        IngestionPipeline,
        loader=loader,
        transformer=cleaner,
        splitter_factory=splitter_factory,
        embedding_manager=embeddings,
        vector_store=vectorstore,
        document_repository=repositories.document,
        document_version_repository=repositories.document_version,
    )

    # Lazy, not eager — constructed on first real use so that the
    # cross-encoder's ~90MB model download doesn't happen at app
    # startup / dev server boot.
    reranker = providers.Singleton(
        CrossEncoderReranker,
    )

    retriever = providers.Singleton(
        RetrieverFactory.create,
        vector_store=vectorstore,
    )

    retriever_manager = providers.Singleton(
        RetrieverManager,
        retriever=retriever,
    )

    knowledge_manager = providers.Factory(
        KnowledgeManager,
        ingestion_pipeline=ingestion_pipeline,
        embedding_manager=embeddings,
        retriever_manager=retriever_manager,
    )
