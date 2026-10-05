# API key repository
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.models.api_key import ApiKey
from packages.infrastructure.repositories.base import BaseRepository


class ApiKeyRepository(BaseRepository[ApiKey]):
    """Repository for API keys (docs/BUGS.md item 33)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ApiKey, session)

    async def get_by_hash(self, key_hash: str) -> ApiKey | None:
        """
        No tenant filter — the hash alone must identify which tenant a key belongs to, since the
        caller's tenant isn't known yet at the point this runs (packages/auth/service.py resolves
        identity, including tenant_id, from the key itself).
        """
        stmt = select(ApiKey).where(ApiKey.key_hash == key_hash)
        return await self.scalar(stmt)

    async def list_by_tenant(self, tenant_id: UUID) -> list[ApiKey]:
        stmt = select(ApiKey).where(ApiKey.tenant_id == tenant_id).order_by(ApiKey.created_at.desc())
        return await self.scalars(stmt)

    async def touch_last_used(self, key: ApiKey) -> None:
        key.last_used_at = datetime.now(UTC)
        await self.session.flush()

    async def revoke(self, key: ApiKey) -> ApiKey:
        key.is_active = False
        key.revoked_at = datetime.now(UTC)
        return await self.update(key)
