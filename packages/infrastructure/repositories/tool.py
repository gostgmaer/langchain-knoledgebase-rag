# Tool repository
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.models.tool import Tool
from packages.infrastructure.repositories.base import BaseRepository


class ToolRepository(BaseRepository[Tool]):
    """Repository for registered tools."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Tool, session)

    async def get_by_name(
        self,
        name: str,
    ) -> Tool | None:
        stmt = (
            select(Tool)
            .where(func.lower(Tool.name) == name.lower())
        )

        return await self.scalar(stmt)

    async def list_enabled(self) -> list[Tool]:
        stmt = (
            select(Tool)
            .where(Tool.enabled.is_(True))
        )

        return await self.scalars(stmt)