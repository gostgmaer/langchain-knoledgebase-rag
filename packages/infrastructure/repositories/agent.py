# Agent repository
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.models.agent import Agent
from packages.infrastructure.repositories.base import BaseRepository


class AgentRepository(BaseRepository[Agent]):
    """Repository for Agent entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Agent, session)

    async def get_by_name(
        self,
        name: str,
    ) -> Agent | None:
        stmt = (
            select(Agent)
            .where(func.lower(Agent.name) == name.lower())
        )

        return await self.scalar(stmt)

    async def get_by_tenant_and_name(
        self,
        tenant_id: UUID,
        name: str,
    ) -> Agent | None:
        stmt = (
            select(Agent)
            .where(
                Agent.tenant_id == tenant_id,
                func.lower(Agent.name) == name.lower(),
            )
        )

        return await self.scalar(stmt)

    async def list_enabled(self) -> list[Agent]:
        stmt = (
            select(Agent)
            .where(Agent.is_active.is_(True))
            .order_by(Agent.name)
        )

        return await self.scalars(stmt)

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Agent]:
        stmt = (
            select(Agent)
            .where(Agent.tenant_id == tenant_id)
            .order_by(Agent.name)
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
            .select_from(Agent)
            .where(Agent.tenant_id == tenant_id)
        )

        return int(await self.session.scalar(stmt) or 0)