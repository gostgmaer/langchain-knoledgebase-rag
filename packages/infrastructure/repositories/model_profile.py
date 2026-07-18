# Model profile repository
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.models.model_profile import ModelProfile
from packages.infrastructure.repositories.base import BaseRepository


class ModelProfileRepository(BaseRepository[ModelProfile]):
    """Repository for AI model profiles."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ModelProfile, session)

    async def get_by_name(
        self,
        name: str,
    ) -> ModelProfile | None:
        stmt = (
            select(ModelProfile)
            .where(func.lower(ModelProfile.name) == name.lower())
        )

        return await self.scalar(stmt)

    async def list_active(self) -> list[ModelProfile]:
        stmt = (
            select(ModelProfile)
            .where(ModelProfile.enabled.is_(True))
        )

        return await self.scalars(stmt)