# Knowledge graph entity repository
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.models.entity import Entity
from packages.domain.models.entity_mention import EntityMention
from packages.infrastructure.repositories.base import BaseRepository


class EntityRepository(BaseRepository[Entity]):
    """Repository for knowledge-graph Entity rows."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Entity, session)

    async def get_by_name(
        self,
        tenant_id: UUID,
        name_lower: str,
        entity_type: str | None,
    ) -> Entity | None:
        """Look up an existing entity by its dedup key (tenant, lowercased
        name, type)."""
        stmt = select(Entity).where(
            Entity.tenant_id == tenant_id,
            Entity.name_lower == name_lower,
            Entity.entity_type == entity_type,
        )

        return await self.scalar(stmt)

    async def get_or_create(
        self,
        tenant_id: UUID,
        name: str,
        entity_type: str | None,
        description: str | None,
    ) -> Entity:
        """Reuse an existing entity across documents rather than
        duplicating it every time a new document mentions it."""
        name_lower = name.strip().lower()

        existing = await self.get_by_name(tenant_id, name_lower, entity_type)
        if existing is not None:
            return existing

        entity = Entity(
            tenant_id=tenant_id,
            name=name,
            name_lower=name_lower,
            entity_type=entity_type,
            description=description,
        )

        return await self.create(entity)

    async def add_mention(
        self,
        entity_id: UUID,
        document_id: UUID,
        tenant_id: UUID,
    ) -> None:
        """Record that this document mentions this entity, if not already
        recorded — check-then-insert, this codebase doesn't use
        ON CONFLICT anywhere else."""
        stmt = select(EntityMention).where(
            EntityMention.entity_id == entity_id,
            EntityMention.document_id == document_id,
        )

        existing = await self.session.scalar(stmt)
        if existing is not None:
            return

        self.session.add(
            EntityMention(
                tenant_id=tenant_id,
                entity_id=entity_id,
                document_id=document_id,
            )
        )
        await self.session.flush()

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int = 2000,
    ) -> list[Entity]:
        """All entities known for a tenant — the candidate pool
        GraphRAGRetriever substring-matches a query against."""
        stmt = (
            select(Entity)
            .where(Entity.tenant_id == tenant_id)
            .limit(limit)
        )

        return await self.scalars(stmt)

    async def list_mentioned_document_ids(
        self,
        entity_ids: list[UUID],
    ) -> list[UUID]:
        """Every distinct document that mentions any of the given
        entities."""
        if not entity_ids:
            return []

        stmt = (
            select(EntityMention.document_id)
            .where(EntityMention.entity_id.in_(entity_ids))
            .distinct()
        )

        result = await self.session.execute(stmt)

        return [row[0] for row in result.all()]
