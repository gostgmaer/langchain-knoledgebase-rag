# Conversation history
from __future__ import annotations

from uuid import UUID

from packages.domain.models.message import Message
from packages.infrastructure.repositories.message import (
    MessageRepository,
)


class ConversationHistory:
    """Loads conversation history."""

    def __init__(
        self,
        repository: MessageRepository,
    ) -> None:
        self.repository = repository

    async def load(
        self,
        conversation_id: UUID,
        *,
        limit: int = 20,
    ) -> list[Message]:
        """Load recent conversation history."""
        return await self.repository.last_n(
            conversation_id,
            limit=limit,
        )

    async def latest(
        self,
        conversation_id: UUID,
    ) -> Message | None:
        return await self.repository.latest(
            conversation_id,
        )

    async def count(
        self,
        conversation_id: UUID,
    ) -> int:
        return await self.repository.count_by_conversation(
            conversation_id,
        )