# Tool repository
from __future__ import annotations

from uuid import UUID

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

    async def get_by_tenant_and_slug(
        self,
        tenant_id: UUID,
        slug: str,
    ) -> Tool | None:
        stmt = (
            select(Tool)
            .where(
                Tool.tenant_id == tenant_id,
                func.lower(Tool.slug) == slug.lower(),
            )
        )

        return await self.scalar(stmt)

    async def list_enabled(self) -> list[Tool]:
        stmt = (
            select(Tool)
            .where(Tool.is_active.is_(True))
        )

        return await self.scalars(stmt)

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Tool]:
        stmt = (
            select(Tool)
            .where(Tool.tenant_id == tenant_id)
            .order_by(Tool.name)
            .offset(offset)
            .limit(limit)
        )

        return await self.scalars(stmt)

    async def count_by_tenant(
        self,
        tenant_id: UUID,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Tool)
            .where(Tool.tenant_id == tenant_id)
        )

        return int(await self.session.scalar(stmt) or 0)