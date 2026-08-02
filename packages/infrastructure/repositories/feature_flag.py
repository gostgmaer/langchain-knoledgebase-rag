# Feature flag repository
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.models.feature_flag import FeatureFlag
from packages.infrastructure.repositories.base import BaseRepository


class FeatureFlagRepository(BaseRepository[FeatureFlag]):
    """Repository for FeatureFlag entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(FeatureFlag, session)

    async def get_effective(
        self,
        key: str,
        tenant_id: UUID | None,
    ) -> bool | None:
        """
        Tenant-specific override if one exists, else the global
        (tenant_id IS NULL) default row, else None (caller falls back
        to a static default — no DB row exists for this key at all).
        """

        if tenant_id is not None:
            tenant_row = await self.scalar(
                select(FeatureFlag).where(
                    FeatureFlag.key == key,
                    FeatureFlag.tenant_id == tenant_id,
                )
            )
            if tenant_row is not None:
                return tenant_row.enabled

        global_row = await self.scalar(
            select(FeatureFlag).where(
                FeatureFlag.key == key,
                FeatureFlag.tenant_id.is_(None),
            )
        )

        return global_row.enabled if global_row is not None else None

    async def get_by_key_and_tenant(
        self,
        key: str,
        tenant_id: UUID | None,
    ) -> FeatureFlag | None:
        stmt = select(FeatureFlag).where(FeatureFlag.key == key)
        stmt = stmt.where(
            FeatureFlag.tenant_id == tenant_id
            if tenant_id is not None
            else FeatureFlag.tenant_id.is_(None)
        )
        return await self.scalar(stmt)

    async def list_all(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[FeatureFlag]:
        stmt = (
            select(FeatureFlag)
            .order_by(FeatureFlag.key.asc())
            .offset(offset)
            .limit(limit)
        )
        return await self.scalars(stmt)
