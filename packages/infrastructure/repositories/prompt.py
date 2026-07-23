# Prompt repository
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.models.prompt import Prompt
from packages.infrastructure.repositories.base import BaseRepository


class PromptRepository(BaseRepository[Prompt]):
    """Repository for prompt templates."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Prompt, session)

    async def get_by_slug(
        self,
        slug: str,
    ) -> Prompt | None:
        stmt = (
            select(Prompt)
            .where(func.lower(Prompt.slug) == slug.lower())
        )

        return await self.scalar(stmt)

    async def get_by_tenant_and_slug(
        self,
        tenant_id: UUID,
        slug: str,
    ) -> Prompt | None:
        stmt = (
            select(Prompt)
            .where(
                Prompt.tenant_id == tenant_id,
                func.lower(Prompt.slug) == slug.lower(),
            )
        )

        return await self.scalar(stmt)

    async def list_active(self) -> list[Prompt]:
        stmt = (
            select(Prompt)
            .where(Prompt.is_active.is_(True))
        )

        return await self.scalars(stmt)

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Prompt]:
        stmt = (
            select(Prompt)
            .where(Prompt.tenant_id == tenant_id)
            .order_by(Prompt.name)
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
            .select_from(Prompt)
            .where(Prompt.tenant_id == tenant_id)
        )

        return int(await self.session.scalar(stmt) or 0)