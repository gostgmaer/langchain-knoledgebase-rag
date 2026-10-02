# Container conversation setup
from __future__ import annotations

from dependency_injector import containers, providers

from packages.conversation.context import ConversationContextBuilder
from packages.conversation.formatter import MessageFormatter
from packages.conversation.history import ConversationHistory


class ConversationContainer(containers.DeclarativeContainer):
    """
    Dependency injection container for the conversation package.

    Only the pieces `packages.application.services.chat_service.ChatService` (the real
    `POST /api/v1/chat` entry point) actually uses: `context`, built from `history`/`formatter`.
    `ConversationManager`/`ConversationService`/`ConversationSummarizer` and their providers
    (`manager`/`service`/`summarizer`) were a now-unused predecessor flow, deleted along with this
    trimming — see docs/UNUSED_FILES.md and docs/CHANGELOG.md for the full account.
    """

    repositories = providers.DependenciesContainer()

    formatter = providers.Singleton(
        MessageFormatter,
    )

    history = providers.Factory(
        ConversationHistory,
        repository=repositories.message,
    )

    context = providers.Factory(
        ConversationContextBuilder,
        history=history,
        formatter=formatter,
    )
