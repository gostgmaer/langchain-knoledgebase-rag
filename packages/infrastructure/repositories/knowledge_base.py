# Knowledge base repository
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.enums.knowledge_base_status import KnowledgeBaseStatus
from packages.domain.models.knowledge_base import KnowledgeBase
from packages.infrastructure.repositories.base import BaseRepository


class KnowledgeBaseRepository(BaseRepository[KnowledgeBase]):
    """Repository for KnowledgeBase entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(KnowledgeBase, session)

    async def get_by_name(
        self,
        name: str,
    ) -> KnowledgeBase | None:
        """Get a knowledge base by name."""
        stmt = (
            select(KnowledgeBase)
            .where(func.lower(KnowledgeBase.name) == name.lower())
        )

        return await self.scalar(stmt)

    async def get_by_tenant_and_name(
        self,
        tenant_id: UUID,
        name: str,
    ) -> KnowledgeBase | None:
        """Get a tenant's knowledge base by name (tenant-scoped)."""
        stmt = (
            select(KnowledgeBase)
            .where(
                KnowledgeBase.tenant_id == tenant_id,
                func.lower(KnowledgeBase.name) == name.lower(),
            )
        )

        return await self.scalar(stmt)

    async def exists_by_name(
        self,
        name: str,
    ) -> bool:
        """Check whether a knowledge base exists."""
        return (
            await self.get_by_name(name)
        ) is not None

    async def list_enabled(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KnowledgeBase]:
        """Return active knowledge bases."""
        stmt = (
            select(KnowledgeBase)
            .where(KnowledgeBase.status == KnowledgeBaseStatus.ACTIVE)
            .offset(offset)
            .limit(limit)
        )

        return await self.scalars(stmt)

    async def count_documents(
        self,
        knowledge_base_id,
    ) -> int:
        from packages.domain.models.document import Document

        stmt = (
            select(func.count())
            .select_from(Document)
            .where(
                Document.knowledge_base_id == knowledge_base_id
            )
        )

        return int(await self.session.scalar(stmt) or 0)