# Container rag setup
from __future__ import annotations

from dependency_injector import containers
from dependency_injector import providers

from packages.rag.embeddings import EmbeddingManager
from packages.rag.indexer import DocumentIndexer
from packages.rag.loader import DocumentLoader
from packages.rag.manager import RAGManager
from packages.rag.pipeline import RAGPipeline
from packages.rag.retriever import RAGRetriever
from packages.rag.splitter import DocumentSplitter
from packages.rag.vectorstore import VectorStoreManager


class RAGContainer(
    containers.DeclarativeContainer,
):

    settings = providers.DependenciesContainer()

    ai = providers.DependenciesContainer()

    embeddings = providers.Singleton(
        EmbeddingManager,
        ai=ai.manager,
    )

    vectorstore = providers.Singleton(
        VectorStoreManager,
        settings=settings.config,
        embeddings=embeddings,
    )

    loader = providers.Singleton(
        DocumentLoader,
    )

    splitter = providers.Singleton(
        DocumentSplitter,
    )

    indexer = providers.Singleton(
        DocumentIndexer,
        loader=loader,
        splitter=splitter,
        vectorstore=vectorstore,
    )

    retriever = providers.Singleton(
        RAGRetriever,
        vectorstore=vectorstore,
    )

    pipeline = providers.Singleton(
        RAGPipeline,
        retriever=retriever,
        indexer=indexer,
    )

    manager = providers.Singleton(
        RAGManager,
        embeddings=embeddings,
        vectorstore=vectorstore,
        loader=loader,
        splitter=splitter,
        indexer=indexer,
        retriever=retriever,
        pipeline=pipeline,
    )