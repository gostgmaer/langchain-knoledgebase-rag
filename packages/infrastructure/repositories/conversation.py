# Conversation repository
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.domain.enums.conversation_status import ConversationStatus
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

    async def list_stale_active(
        self,
        older_than: datetime,
        *,
        limit: int = 200,
    ) -> list[Conversation]:
        """
        ACTIVE conversations with no activity since `older_than` —
        Cleanup Jobs' expired-session sweep (docs/mvpRAG.md v1.1).
        """
        stmt = (
            select(Conversation)
            .where(
                Conversation.status == ConversationStatus.ACTIVE,
                Conversation.last_message_at.is_not(None),
                Conversation.last_message_at < older_than,
            )
            .limit(limit)
        )

        return await self.scalars(stmt)

    async def list_stuck_processing(
        self,
        older_than: datetime,
        *,
        limit: int = 200,
    ) -> list[Conversation]:
        """
        Conversations left `PROCESSING` since before `older_than` —
        Durable Execution's crash-detection sweep (docs/mvpRAG.md
        v2.0, recover_stuck_conversations_job). Mirrors
        `list_stale_active()`'s shape exactly, just against the
        `processing_started_at` marker ChatService sets right before
        invoking/resuming the graph instead of `last_message_at`.
        """
        stmt = (
            select(Conversation)
            .where(
                Conversation.status == ConversationStatus.PROCESSING,
                Conversation.processing_started_at.is_not(None),
                Conversation.processing_started_at < older_than,
            )
            .limit(limit)
        )

        return await self.scalars(stmt)

    async def mark_status(
        self,
        conversation: Conversation,
        status: ConversationStatus,
    ) -> Conversation:
        """
        Sets `.status` directly — NOT via `archive()`/`restore()` above,
        which set a column-less `is_archived` attribute that silently
        never persists (Conversation has no such mapped column, only
        `status`). Confirmed live while building the Cleanup Jobs
        completion feature; kept `archive()`/`restore()` unchanged since
        fixing them wasn't in scope here.
        """
        conversation.status = status

        return await self.update(conversation)

    async def mark_processing(
        self,
        conversation: Conversation,
    ) -> Conversation:
        """
        Durable Execution (docs/mvpRAG.md v2.0) — called right before
        ChatService invokes/resumes the graph. A dedicated method
        rather than `mark_status(..., PROCESSING)` because this needs
        to set `processing_started_at` in the same write, not just
        `.status`.
        """
        conversation.status = ConversationStatus.PROCESSING
        conversation.processing_started_at = datetime.utcnow()

        return await self.update(conversation)

    async def clear_processing(
        self,
        conversation: Conversation,
    ) -> Conversation:
        """
        Called once the graph's invoke()/resume() call has actually
        returned — whether that's a completed turn or a legitimate
        tool-approval pause, both mean the call itself didn't crash,
        so this always resets back to ACTIVE. Only a real process
        death mid-call skips this entirely, leaving `status` at
        `PROCESSING` and `processing_started_at` stale — the exact
        signal `list_stuck_processing()` looks for.
        """
        conversation.status = ConversationStatus.ACTIVE
        conversation.processing_started_at = None

        return await self.update(conversation)