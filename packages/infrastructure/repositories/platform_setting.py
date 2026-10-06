# Platform setting repository
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.models.platform_setting import PlatformSetting
from packages.infrastructure.repositories.base import BaseRepository


class PlatformSettingRepository(BaseRepository[PlatformSetting]):
    """Repository for PlatformSetting entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(PlatformSetting, session)

    async def get_by_key(self, key: str) -> PlatformSetting | None:
        return await self.scalar(select(PlatformSetting).where(PlatformSetting.key == key))

    async def list_all(self) -> list[PlatformSetting]:
        return await self.scalars(select(PlatformSetting).order_by(PlatformSetting.key.asc()))
