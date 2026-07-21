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
from packages.knowledge.retrievers.manager import RetrieverManager
from packages.knowledge.retrievers.providers.similarity import (
    SimilarityRetriever,
)
from packages.knowledge.splitters.recursive import RecursiveDocumentSplitter
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
    splitting, real embeddings, and a real Chroma-backed vector store.
    """

    settings = providers.DependenciesContainer()

    ai = providers.DependenciesContainer()

    services = providers.DependenciesContainer()

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

    splitter = providers.Singleton(
        RecursiveDocumentSplitter,
    )

    ingestion_pipeline = providers.Singleton(
        IngestionPipeline,
        loader=loader,
        transformer=cleaner,
        splitter=splitter,
        embedding_manager=embeddings,
        vector_store=vectorstore,
    )

    similarity_retriever = providers.Singleton(
        SimilarityRetriever,
        vector_store=vectorstore,
    )

    retriever_manager = providers.Singleton(
        RetrieverManager,
        retriever=similarity_retriever,
    )

    knowledge_manager = providers.Singleton(
        KnowledgeManager,
        ingestion_pipeline=ingestion_pipeline,
        embedding_manager=embeddings,
        retriever_manager=retriever_manager,
    )
