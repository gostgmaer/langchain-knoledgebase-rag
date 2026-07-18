# Container services setup
from __future__ import annotations

from dependency_injector import containers
from dependency_injector import providers

from packages.chat.chat_service import ChatService


class ServiceContainer(containers.DeclarativeContainer):
    """
    Registers application services.

    Business services that are shared between API,
    workers, graphs and background jobs belong here.
    """

    ai = providers.DependenciesContainer()

    repositories = providers.DependenciesContainer()

    #
    # AI Services
    #

    chat = providers.Singleton(
        ChatService,
        ai=ai.manager,
    )

    #
    # Future Services
    #

    # prompt = providers.Singleton(
    #     PromptService,
    #     repository=repositories.prompt,
    # )

    # document = providers.Singleton(
    #     DocumentService,
    #     repository=repositories.document,
    # )

    # knowledge_base = providers.Singleton(
    #     KnowledgeBaseService,
    #     repository=repositories.knowledge_base,
    # )

    # tool = providers.Singleton(
    #     ToolService,
    #     repository=repositories.tool,
    # )

    # agent = providers.Singleton(
    #     AgentService,
    #     repository=repositories.agent,
    # )

    # model_profile = providers.Singleton(
    #     ModelProfileService,
    #     repository=repositories.model_profile,
    # )