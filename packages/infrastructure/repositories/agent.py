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
            .where(Agent.enabled.is_(True))
            .order_by(Agent.name)
        )

        return await self.scalars(stmt)