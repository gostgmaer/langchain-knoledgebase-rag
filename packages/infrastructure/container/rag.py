# Container rag setup
from __future__ import annotations

from dependency_injector import containers
from dependency_injector import providers

from packages.rag.embeddings import EmbeddingManager
from packages.rag.indexer import DocumentIndexer
from packages.rag.loader import DocumentLoader
from packages.rag.manager import RAGManager
from packages.rag.pipeline import RAGPipeline
from packages.rag.pipelines.retrieval import RetrievalPipeline
from packages.rag.splitter import DocumentSplitter
from packages.rag.vectorstore import VectorStoreManager
from packages.knowledge.manager import KnowledgeManager
from packages.rag.builders.context import ContextBuilder
from packages.rag.builders.prompt import PromptBuilder
from packages.rag.builders.citation import CitationBuilder


class RAGContainer(
    containers.DeclarativeContainer,
):

    settings = providers.DependenciesContainer()

    ai = providers.DependenciesContainer()

    services = providers.DependenciesContainer()

    embeddings = providers.Singleton(
        EmbeddingManager,
    )

    vectorstore = providers.Singleton(
        VectorStoreManager,
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
        embeddings=embeddings,
        vectorstore=vectorstore,
    )

    knowledge_manager = providers.Singleton(
        KnowledgeManager,
        ingestion_pipeline=providers.Object(None),
        embedding_manager=providers.Object(None),
        retriever_manager=providers.Object(None),
    )

    retriever = providers.Singleton(
        RetrievalPipeline,
        vectorstore=vectorstore,
    )

    pipeline = providers.Singleton(
        RAGPipeline,
        retriever=retriever,
        indexer=indexer,
    )

    context_builder = providers.Singleton(ContextBuilder)
    prompt_builder = providers.Singleton(PromptBuilder)
    citation_builder = providers.Singleton(CitationBuilder)

    manager = providers.Singleton(
        RAGManager,
        retrieval_pipeline=retriever,
        context_builder=context_builder,
        prompt_builder=prompt_builder,
        citation_builder=citation_builder,
        chat_service=services.chat,
    )