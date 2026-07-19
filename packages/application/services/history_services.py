from __future__ import annotations

from packages.domain.models.conversation import Conversation
from packages.domain.models.message import Message
from packages.domain.repositories.message import MessageRepository


class HistoryService:
    """
    Provides conversation history for prompt construction.
    """

    def __init__(
        self,
        repository: MessageRepository,
    ) -> None:
        self._repository = repository

    async def get_history(
        self,
        conversation: Conversation,
        limit: int = 20,
    ) -> list[Message]:
        """
        Returns the latest conversation messages ordered chronologically.
        """

        messages = await self._repository.list_by_conversation(
            conversation.id,
            limit=limit,
        )

        return sorted(
            messages,
            key=lambda message: message.created_at,
        )