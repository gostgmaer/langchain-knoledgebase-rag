# Container memory setup
from __future__ import annotations

from dependency_injector import containers, providers

from packages.memory.checkpoint import CheckpointFactory
from packages.memory.implementations.llm_extractor import LLMMemoryExtractor
from packages.memory.implementations.llm_summarizer import LLMMemorySummarizer
from packages.memory.implementations.pgvector_retriever import PgVectorMemoryRetriever
from packages.memory.implementations.postgres_store import PostgresMemoryStore
from packages.memory.manager import MemoryManager
from packages.memory.strategy import MemoryStrategy


class MemoryContainer(containers.DeclarativeContainer):

    settings = providers.DependenciesContainer()
    database = providers.DependenciesContainer()
    ai = providers.DependenciesContainer()
    rag = providers.DependenciesContainer()
    repositories = providers.DependenciesContainer()

    # Singleton, not Factory (docs/BUGS.md item 69) — store/retriever hold only a session_factory
    # now, not an already-bound per-request MemoryRepository, so there's nothing request-scoped
    # left to capture. This is what lets `manager` below, and therefore the graph's `load_memory`
    # node, become Singleton too.
    store = providers.Singleton(
        PostgresMemoryStore,
        session_factory=database.session_factory,
        embeddings=rag.embeddings,
    )

    extractor = providers.Singleton(
        LLMMemoryExtractor,
        llm=ai.manager,
    )

    summarizer = providers.Singleton(
        LLMMemorySummarizer,
        llm=ai.manager,
    )

    retriever = providers.Singleton(
        PgVectorMemoryRetriever,
        session_factory=database.session_factory,
        embeddings=rag.embeddings,
    )

    checkpoint = providers.Singleton(
        CheckpointFactory,
        strategy=MemoryStrategy.MEMORY,
    )

    manager = providers.Singleton(
        MemoryManager,
        store=store,
        extractor=extractor,
        summarizer=summarizer,
        retriever=retriever,
    )