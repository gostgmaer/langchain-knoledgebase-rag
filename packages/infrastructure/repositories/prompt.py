# Prompt repository
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.models.prompt import Prompt
from packages.infrastructure.repositories.base import BaseRepository


class PromptRepository(BaseRepository[Prompt]):
    """Repository for prompt templates."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Prompt, session)

    async def get_by_key(
        self,
        key: str,
    ) -> Prompt | None:
        stmt = (
            select(Prompt)
            .where(func.lower(Prompt.key) == key.lower())
        )

        return await self.scalar(stmt)

    async def list_active(self) -> list[Prompt]:
        stmt = (
            select(Prompt)
            .where(Prompt.enabled.is_(True))
        )

        return await self.scalars(stmt)