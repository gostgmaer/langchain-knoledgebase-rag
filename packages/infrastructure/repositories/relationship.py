# Knowledge graph relationship (edge) repository
from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.models.relationship import Relationship
from packages.infrastructure.repositories.base import BaseRepository


class RelationshipRepository(BaseRepository[Relationship]):
    """Repository for knowledge-graph Relationship (edge) rows."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Relationship, session)

    async def get_or_create(
        self,
        tenant_id: UUID,
        source_entity_id: UUID,
        target_entity_id: UUID,
        relationship_type: str | None,
        description: str | None,
        document_id: UUID,
    ) -> Relationship:
        """Reuse an existing edge if the same source/target/type triple
        was already extracted from an earlier document."""
        stmt = select(Relationship).where(
            Relationship.source_entity_id == source_entity_id,
            Relationship.target_entity_id == target_entity_id,
            Relationship.relationship_type == relationship_type,
        )

        existing = await self.scalar(stmt)
        if existing is not None:
            return existing

        relationship = Relationship(
            tenant_id=tenant_id,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relationship_type=relationship_type,
            description=description,
            document_id=document_id,
        )

        return await self.create(relationship)

    async def list_neighbors(
        self,
        entity_ids: list[UUID],
    ) -> list[Relationship]:
        """1-hop relationships touching any of the given entities, as
        either source or target."""
        if not entity_ids:
            return []

        stmt = select(Relationship).where(
            or_(
                Relationship.source_entity_id.in_(entity_ids),
                Relationship.target_entity_id.in_(entity_ids),
            )
        )

        return await self.scalars(stmt)
