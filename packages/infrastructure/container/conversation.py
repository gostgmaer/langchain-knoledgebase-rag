# Container conversation setup
from __future__ import annotations

from dependency_injector import containers
from dependency_injector import providers

from packages.conversation.context import ConversationContextBuilder
from packages.conversation.formatter import MessageFormatter
from packages.conversation.history import ConversationHistory
from packages.conversation.manager import ConversationManager
from packages.conversation.service import ConversationService
from packages.conversation.summarizer import ConversationSummarizer


class ConversationContainer(containers.DeclarativeContainer):
    """Dependency injection container for the conversation package."""

    repositories = providers.DependenciesContainer()
    graph = providers.DependenciesContainer()
    services = providers.DependenciesContainer()

    formatter = providers.Singleton(
        MessageFormatter,
    )

    history = providers.Factory(
        ConversationHistory,
        repository=repositories.message,
    )

    service = providers.Factory(
        ConversationService,
        conversations=repositories.conversation,
        messages=repositories.message,
    )

    context = providers.Factory(
        ConversationContextBuilder,
        history=history,
        formatter=formatter,
    )

    summarizer = providers.Factory(
        ConversationSummarizer,
        chat=services.chat,
    )

    manager = providers.Factory(
        ConversationManager,
        service=service,
        context=context,
        graph=graph.manager,
    )