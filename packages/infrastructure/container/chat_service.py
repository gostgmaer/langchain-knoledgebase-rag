# Container chat service setup
from __future__ import annotations

from dependency_injector import containers, providers

from packages.application.services.chat_service import ChatService
from packages.application.services.conversation_service import ConversationService
from packages.application.services.message_service import MessageService


class ChatServiceContainer(containers.DeclarativeContainer):
    """
    Wires the packages.application ChatService/ConversationService/
    MessageService trio — the top-level chat entry point, replacing
    ConversationManager's flow.
    """

    database = providers.DependenciesContainer()
    graph = providers.DependenciesContainer()
    conversation = providers.DependenciesContainer()

    conversation_service = providers.Factory(
        ConversationService,
        uow=database.uow,
    )

    message_service = providers.Factory(
        MessageService,
        uow=database.uow,
    )

    chat_service = providers.Factory(
        ChatService,
        uow=database.uow,
        conversation_service=conversation_service,
        message_service=message_service,
        graph=graph.manager,
        context=conversation.context,
    )
