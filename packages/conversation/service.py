# Conversation service
from __future__ import annotations

from uuid import UUID

from packages.domain.models.conversation import Conversation
from packages.domain.models.message import Message
from packages.infrastructure.repositories.conversation import (
    ConversationRepository,
)
from packages.infrastructure.repositories.message import (
    MessageRepository,
)


class ConversationService:
    """Business logic for conversations."""

    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
    ) -> None:
        self.conversations = conversations
        self.messages = messages

    async def create(
        self,
        conversation: Conversation,
    ) -> Conversation:
        return await self.conversations.create(conversation)

    async def get(
        self,
        conversation_id: UUID,
    ) -> Conversation | None:
        return await self.conversations.get(conversation_id)

    async def add_message(
        self,
        message: Message,
    ) -> Message:
        return await self.messages.create(message)

    async def list_messages(
        self,
        conversation_id: UUID,
    ) -> list[Message]:
        return await self.messages.list_by_conversation(
            conversation_id
        )

    async def latest_message(
        self,
        conversation_id: UUID,
    ) -> Message | None:
        return await self.messages.latest(
            conversation_id
        )