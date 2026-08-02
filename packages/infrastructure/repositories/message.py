# Message repository
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.models.conversation import Conversation
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

    async def sum_usage_by_tenant(
        self,
        tenant_id: UUID,
        *,
        since: datetime | None = None,
    ) -> dict:
        """
        Total prompt/completion/total tokens and cost across every
        message belonging to a tenant's conversations. Message has no
        tenant_id of its own (only its parent Conversation does), so
        this joins through Conversation — the same two-hop pattern
        already used for tenant-scoping Feedback elsewhere in this app.
        """

        stmt = (
            select(
                func.coalesce(func.sum(Message.prompt_tokens), 0),
                func.coalesce(func.sum(Message.completion_tokens), 0),
                func.coalesce(func.sum(Message.total_tokens), 0),
                func.coalesce(func.sum(Message.cost), 0),
            )
            .select_from(Message)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(Conversation.tenant_id == tenant_id)
        )

        if since is not None:
            stmt = stmt.where(Message.created_at >= since)

        prompt_tokens, completion_tokens, total_tokens, cost = (
            await self.session.execute(stmt)
        ).one()

        return {
            "prompt_tokens": int(prompt_tokens),
            "completion_tokens": int(completion_tokens),
            "total_tokens": int(total_tokens),
            "cost": Decimal(cost),
        }

    async def sum_usage_by_tenant_daily(
        self,
        tenant_id: UUID,
        *,
        days: int = 30,
    ) -> list[dict]:
        """Daily token/cost breakdown for a tenant over the last N days."""

        since = datetime.now(UTC) - timedelta(days=days)
        day = func.date(Message.created_at)

        stmt = (
            select(
                day.label("day"),
                func.coalesce(func.sum(Message.total_tokens), 0),
                func.coalesce(func.sum(Message.cost), 0),
            )
            .select_from(Message)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Conversation.tenant_id == tenant_id,
                Message.created_at >= since,
            )
            .group_by(day)
            .order_by(day)
        )

        rows = (await self.session.execute(stmt)).all()

        return [
            {
                "date": str(row[0]),
                "total_tokens": int(row[1]),
                "cost": Decimal(row[2]),
            }
            for row in rows
        ]

    async def count_by_tenant_daily(
        self,
        tenant_id: UUID,
        *,
        days: int = 30,
    ) -> list[dict]:
        """Daily message count for a tenant over the last N days (Analytics)."""

        since = datetime.now(UTC) - timedelta(days=days)
        day = func.date(Message.created_at)

        stmt = (
            select(day.label("day"), func.count())
            .select_from(Message)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Conversation.tenant_id == tenant_id,
                Message.created_at >= since,
            )
            .group_by(day)
            .order_by(day)
        )

        rows = (await self.session.execute(stmt)).all()

        return [{"date": str(row[0]), "count": int(row[1])} for row in rows]

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