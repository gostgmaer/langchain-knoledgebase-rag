# Container application setup
from __future__ import annotations

from dependency_injector import containers

from .ai import AIContainer
from .conversation import ConversationContainer
from .database import DatabaseContainer
from .graph import GraphContainer
from .memory import MemoryContainer
from .rag import RAGContainer
from .repositories import RepositoryContainer
from .services import ServiceContainer
from .settings import SettingsContainer
from .tools import ToolsContainer


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