# Memory repository
from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.models.memory import Memory
from packages.infrastructure.repositories.base import BaseRepository


class MemoryRepository(BaseRepository[Memory]):
    """Repository for long-term Memory entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Memory, session)

    async def search_similar(
        self,
        *,
        tenant_id: UUID,
        query_vector: list[float],
        user_id: UUID | None = None,
        k: int = 5,
    ) -> list[Memory]:
        stmt = select(Memory).where(Memory.tenant_id == tenant_id)

        if user_id is not None:
            stmt = stmt.where(Memory.user_id == user_id)

        stmt = stmt.order_by(
            Memory.vector.cosine_distance(query_vector)
        ).limit(k)

        return await self.scalars(stmt)

    async def delete_by_conversation(
        self,
        conversation_id: UUID,
    ) -> None:
        stmt = delete(Memory).where(
            Memory.conversation_id == conversation_id
        )
        await self.session.execute(stmt)
        await self.session.flush()
