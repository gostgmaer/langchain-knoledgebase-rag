# Feedback repository
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.enums.feedback_rating import FeedbackRating
from packages.domain.models.feedback import Feedback
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
