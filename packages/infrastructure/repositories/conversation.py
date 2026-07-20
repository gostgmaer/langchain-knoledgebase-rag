# Conversation repository
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.domain.models.conversation import Conversation
from packages.infrastructure.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    """Repository for Conversation entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Conversation, session)

    async def get_by_session_id(
        self,
        session_id: str,
    ) -> Conversation | None:
        """Retrieve a conversation by its session ID."""
        stmt = select(Conversation).where(
            Conversation.session_id == session_id
        )
        return await self.scalar(stmt)

    async def get_with_messages(
        self,
        conversation_id: UUID,
    ) -> Conversation | None:
        """Retrieve a conversation with all its messages."""
        stmt = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(Conversation.id == conversation_id)
        )
        return await self.scalar(stmt)

    async def list_active(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Conversation]:
        """Return active conversations."""
        stmt = (
            select(Conversation)
            .where(Conversation.is_deleted.is_(False))
            .offset(offset)
            .limit(limit)
        )

        return await self.scalars(stmt)

    async def archive(
        self,
        conversation: Conversation,
    ) -> Conversation:
        """Archive a conversation."""
        conversation.is_archived = True

        await self.session.flush()
        await self.session.refresh(conversation)

        return conversation

    async def restore(
        self,
        conversation: Conversation,
    ) -> Conversation:
        """Restore an archived conversation."""
        conversation.is_archived = False

        await self.session.flush()
        await self.session.refresh(conversation)

        return conversation