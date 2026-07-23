# Container application setup
from __future__ import annotations

from dependency_injector import containers, providers
from packages.infrastructure.container.chat_service import ChatServiceContainer
from packages.infrastructure.container.conversation import ConversationContainer

from .ai import AIContainer

# from package.conversation import ConversationContainer
from packages.infrastructure.container.database import DatabaseContainer
from packages.infrastructure.container.graph import GraphContainer
from packages.infrastructure.container.iam import IAMContainer
from packages.infrastructure.container.memory import MemoryContainer
from packages.infrastructure.container.queue import QueueContainer
from packages.infrastructure.container.rag import RAGContainer
from packages.infrastructure.container.repositories import RepositoryContainer
from packages.infrastructure.container.services import ServiceContainer
from packages.infrastructure.container.settings import SettingsContainer
from packages.infrastructure.container.tools import ToolsContainer
from packages.infrastructure.container.upload import UploadContainer


class ApplicationContainer(containers.DeclarativeContainer):
    """
    Root dependency injection container.

    This container composes the complete application.
    """

    wiring_config = containers.WiringConfiguration(
        packages=[
            "packages.api",
            # "packages.workers",
        ]
    )

    #
    # Core
    #

    settings = providers.Container(SettingsContainer)

    database = providers.Container(
        DatabaseContainer,
        settings=settings,
    )

    repositories = providers.Container(
        RepositoryContainer,
        database=database,
    )

    #
    # IAM
    #

    iam = providers.Container(
        IAMContainer,
    )

    #
    # Upload Service
    #

    upload = providers.Container(
        UploadContainer,
    )

    #
    # Background job queue (arq) — producer side only, see
    # packages/infrastructure/container/queue.py
    #

    queue = providers.Container(
        QueueContainer,
    )

    #
    # AI
    #

    ai = providers.Container(
        AIContainer,
        settings=settings,
    )

    #
    # Shared Services
    #

    services = providers.Container(
        ServiceContainer,
        ai=ai,
        repositories=repositories,
    )

    rag = providers.Container(
        RAGContainer,
        settings=settings,
        ai=ai,
        services=services,
        repositories=repositories,
    )

    # Declared after `rag` — the knowledge-base/document-search tools need
    # rag.knowledge_manager (see packages/infrastructure/container/tools.py).
    tools = providers.Container(
        ToolsContainer,
        settings=settings,
        rag=rag,
    )

    memory = providers.Container(
        MemoryContainer,
        settings=settings,
        database=database,
        ai=ai,
        rag=rag,
        repositories=repositories,
    )

    #
    # LangGraph
    #

    graph = providers.Container(
        GraphContainer,
        settings=settings,
        ai=ai,
        rag=rag,
        tools=tools,
        memory=memory,
        services=services,
    )

    #
    # Conversation
    #

    conversation = providers.Container(
        ConversationContainer,
        repositories=repositories,
        graph=graph,
        services=services,
    )

    #
    # Chat (top-level entry point)
    #

    chat_service = providers.Container(
        ChatServiceContainer,
        database=database,
        graph=graph,
        conversation=conversation,
    )
