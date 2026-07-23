# AI response repository
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.models.ai_response import AIResponse
from packages.infrastructure.repositories.base import BaseRepository


class AIResponseRepository(BaseRepository[AIResponse]):
    """Repository for AIResponse entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AIResponse, session)

    async def get_by_message(
        self,
        message_id: UUID,
    ) -> AIResponse | None:
        stmt = select(AIResponse).where(
            AIResponse.message_id == message_id,
        )

        return await self.scalar(stmt)
