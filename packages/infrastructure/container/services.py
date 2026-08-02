# Container services setup
from __future__ import annotations

from dependency_injector import containers
from dependency_injector import providers

from packages.chat.chat_service import ChatService
from packages.config.loader import settings as _settings
from packages.infrastructure.resilience.circuit_breaker import CircuitBreaker


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

    # One breaker per process, shared by every chat() / astream() /
    # etc. call — this app only ever has one active provider config at
    # a time (packages/config/ai.py's AISettings), so there's no need
    # to key a registry by provider name the way RetryTransport does
    # per-host.
    llm_circuit_breaker = providers.Singleton(
        CircuitBreaker,
        name="llm-provider",
        failure_threshold=_settings.ai.circuit_breaker_failure_threshold,
        reset_timeout_seconds=_settings.ai.circuit_breaker_reset_seconds,
    )

    chat = providers.Singleton(
        ChatService,
        llm=ai.manager,
        breaker=llm_circuit_breaker,
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