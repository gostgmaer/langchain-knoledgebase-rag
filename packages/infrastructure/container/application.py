# Container application setup
from __future__ import annotations

from dependency_injector import containers

from packages.infrastructure.container.conversation import ConversationContainer

from .ai import AIContainer
# from package.conversation import ConversationContainer
from packages.infrastructure.container.database import DatabaseContainer
from packages.infrastructure.container.graph import GraphContainer
from packages.infrastructure.container.memory import MemoryContainer
from packages.infrastructure.container.rag import RAGContainer
from packages.infrastructure.container.repositories import RepositoryContainer
from packages.infrastructure.container.services import ServiceContainer
from packages.infrastructure.container.settings import SettingsContainer
from packages.infrastructure.container.tools import ToolsContainer


class ApplicationContainer(containers.DeclarativeContainer):
    """
    Root dependency injection container.

    This container composes the complete application.
    """

    wiring_config = containers.WiringConfiguration(
        packages=[
            "packages.api",
            "packages.workers",
        ]
    )

    #
    # Core
    #

    settings = containers.Container(
        SettingsContainer,
    )

    database = containers.Container(
        DatabaseContainer,
        settings=settings,
    )

    repositories = containers.Container(
        RepositoryContainer,
        database=database,
    )

    #
    # AI
    #

    ai = containers.Container(
        AIContainer,
        settings=settings,
    )

    rag = containers.Container(
        RAGContainer,
        settings=settings,
        ai=ai,
    )

    tools = containers.Container(
        ToolsContainer,
        settings=settings,
    )

    memory = containers.Container(
        MemoryContainer,
        settings=settings,
    )

    #
    # Shared Services
    #

    services = containers.Container(
        ServiceContainer,
        ai=ai,
        repositories=repositories,
    )

    #
    # LangGraph
    #

    graph = containers.Container(
        GraphContainer,
        ai=ai,
        rag=rag,
        tools=tools,
        memory=memory,
    )

    #
    # Conversation
    #

    conversation = containers.Container(
        ConversationContainer,
        repositories=repositories,
        graph=graph,
        services=services,
    )