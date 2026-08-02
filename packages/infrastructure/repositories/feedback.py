# Feedback repository
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.enums.feedback_rating import FeedbackRating
from packages.domain.models.feedback import Feedback
from packages.domain.models.message import Message
from packages.infrastructure.repositories.base import BaseRepository


class FeedbackRepository(BaseRepository[Feedback]):
    """Repository for Feedback entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Feedback, session)

    async def get_by_user_and_message(
        self,
        user_id: UUID,
        message_id: UUID,
    ) -> Feedback | None:
        stmt = select(Feedback).where(
            Feedback.user_id == user_id,
            Feedback.message_id == message_id,
        )

        return await self.scalar(stmt)

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        rating: FeedbackRating | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Feedback]:
        stmt = select(Feedback).where(Feedback.tenant_id == tenant_id)

        if rating is not None:
            stmt = stmt.where(Feedback.rating == rating)

        stmt = (
            stmt.order_by(Feedback.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        return await self.scalars(stmt)

    async def count_by_tenant(
        self,
        tenant_id: UUID,
        *,
        rating: FeedbackRating | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Feedback)
            .where(Feedback.tenant_id == tenant_id)
        )

        if rating is not None:
            stmt = stmt.where(Feedback.rating == rating)

        return int(await self.session.scalar(stmt) or 0)

    async def count_by_rating_daily(
        self,
        tenant_id: UUID,
        *,
        days: int = 30,
    ) -> list[dict]:
        """Daily thumbs-up/down counts for a tenant — Analytics' feedback-trends series."""

        since = datetime.now(UTC) - timedelta(days=days)
        day = func.date(Feedback.created_at)

        stmt = (
            select(day.label("day"), Feedback.rating, func.count())
            .select_from(Feedback)
            .where(
                Feedback.tenant_id == tenant_id,
                Feedback.created_at >= since,
            )
            .group_by(day, Feedback.rating)
            .order_by(day)
        )

        rows = (await self.session.execute(stmt)).all()

        return [
            {"date": str(row[0]), "rating": row[1].value, "count": int(row[2])}
            for row in rows
        ]

    async def top_negative_feedback_messages(
        self,
        tenant_id: UUID,
        *,
        limit: int = 10,
    ) -> list[dict]:
        """
        Most-thumbs-downed distinct messages for a tenant — Analytics'
        pragmatic definition of "top failing queries" (docs/mvpRAG.md
        v1.1). There's no structured error/exception log to query
        against for a stricter definition; negative feedback is the
        real, buildable signal that already exists.
        """

        stmt = (
            select(
                Feedback.message_id,
                Message.content,
                func.count().label("negative_count"),
            )
            .select_from(Feedback)
            .join(Message, Message.id == Feedback.message_id)
            .where(
                Feedback.tenant_id == tenant_id,
                Feedback.rating == FeedbackRating.THUMBS_DOWN,
            )
            .group_by(Feedback.message_id, Message.content)
            .order_by(func.count().desc())
            .limit(limit)
        )

        rows = (await self.session.execute(stmt)).all()

        return [
            {
                "message_id": str(row[0]),
                "content": row[1],
                "negative_count": int(row[2]),
            }
            for row in rows
        ]
