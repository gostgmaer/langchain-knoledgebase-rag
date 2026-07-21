# Container application setup
from __future__ import annotations

from dependency_injector import containers, providers
from packages.agent.prompt import PromptBuilder
from packages.agent.runtime import AgentRuntime
from packages.infrastructure.container.chat_service import ChatServiceContainer
from packages.infrastructure.container.conversation import ConversationContainer

from .ai import AIContainer

# from package.conversation import ConversationContainer
from packages.infrastructure.container.database import DatabaseContainer
from packages.infrastructure.container.graph import GraphContainer
from packages.infrastructure.container.iam import IAMContainer
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
    # AI
    #

    ai = providers.Container(
        AIContainer,
        settings=settings,
    )

    prompt_builder = providers.Singleton(
        PromptBuilder,
    )

    tools = providers.Container(
        ToolsContainer,
        settings=settings,
    )

    agent_runtime = providers.Singleton(
        AgentRuntime,
        llm=ai.manager,
        prompt_builder=prompt_builder,
        tools=tools.manager,
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
