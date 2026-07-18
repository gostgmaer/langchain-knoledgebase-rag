# Message repository
from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.models.message import Message
from packages.infrastructure.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    """Repository for Message entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Message, session)

    async def list_by_conversation(
        self,
        conversation_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Message]:
        """Return messages for a conversation."""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .offset(offset)
            .limit(limit)
        )

        return await self.scalars(stmt)

    async def latest(
        self,
        conversation_id: UUID,
    ) -> Message | None:
        """Return the latest message in a conversation."""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.created_at))
            .limit(1)
        )

        return await self.scalar(stmt)

    async def last_n(
        self,
        conversation_id: UUID,
        limit: int = 10,
    ) -> list[Message]:
        """Return the last N messages."""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.created_at))
            .limit(limit)
        )

        messages = await self.scalars(stmt)

        return list(reversed(messages))

    async def count_by_conversation(
        self,
        conversation_id: UUID,
    ) -> int:
        """Count messages in a conversation."""
        stmt = (
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == conversation_id)
        )

        return int(await self.session.scalar(stmt) or 0)

    async def delete_by_conversation(
        self,
        conversation_id: UUID,
    ) -> int:
        """Delete all messages for a conversation."""
        messages = await self.list_by_conversation(
            conversation_id,
            limit=100000,
        )

        for message in messages:
            await self.session.delete(message)

        return len(messages)