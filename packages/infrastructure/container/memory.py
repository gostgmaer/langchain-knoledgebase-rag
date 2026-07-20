# Container memory setup
from __future__ import annotations

from dependency_injector import containers
from dependency_injector import providers

from packages.memory.checkpoint import CheckpointFactory
from packages.memory.manager import MemoryManager
from packages.memory.strategy import MemoryStrategy
from packages.memory.implementations.postgres_store import PostgresMemoryStore
from packages.memory.implementations.llm_extractor import LLMMemoryExtractor
from packages.memory.implementations.llm_summarizer import LLMMemorySummarizer
from packages.memory.implementations.pgvector_retriever import PgVectorMemoryRetriever


class MemoryContainer(containers.DeclarativeContainer):

    settings = providers.DependenciesContainer()
    database = providers.DependenciesContainer()
    ai = providers.DependenciesContainer()
    rag = providers.DependenciesContainer()
    repositories = providers.DependenciesContainer()

    store = providers.Factory(
        PostgresMemoryStore,
        repository=repositories.memory,
        embeddings=rag.embeddings,
    )

    extractor = providers.Factory(
        LLMMemoryExtractor,
        llm=ai.manager,
    )

    summarizer = providers.Factory(
        LLMMemorySummarizer,
        llm=ai.manager,
    )

    retriever = providers.Factory(
        PgVectorMemoryRetriever,
        repository=repositories.memory,
        embeddings=rag.embeddings,
    )

    checkpoint = providers.Singleton(
        CheckpointFactory,
        strategy=MemoryStrategy.MEMORY,
    )

    manager = providers.Factory(
        MemoryManager,
        store=store,
        extractor=extractor,
        summarizer=summarizer,
        retriever=retriever,
    )