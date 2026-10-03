# Prompt version repository
from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.enums.prompt_status import PromptStatus
from packages.domain.models.prompt_version import PromptVersion
from packages.infrastructure.repositories.base import BaseRepository


class PromptVersionRepository(BaseRepository[PromptVersion]):
    """Repository for prompt template versions (docs/BUGS.md item 30)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(PromptVersion, session)

    async def list_by_prompt(self, prompt_id: UUID) -> list[PromptVersion]:
        stmt = (
            select(PromptVersion)
            .where(PromptVersion.prompt_id == prompt_id)
            .order_by(desc(PromptVersion.version))
        )

        return await self.scalars(stmt)

    async def get_published(self, prompt_id: UUID) -> PromptVersion | None:
        stmt = select(PromptVersion).where(
            PromptVersion.prompt_id == prompt_id,
            PromptVersion.is_published.is_(True),
        )

        return await self.scalar(stmt)

    async def next_version_number(self, prompt_id: UUID) -> int:
        stmt = select(func.max(PromptVersion.version)).where(PromptVersion.prompt_id == prompt_id)
        current_max = await self.session.scalar(stmt)
        return (current_max or 0) + 1

    async def publish(self, prompt_id: UUID, version: PromptVersion) -> PromptVersion:
        """
        Makes `version` the one live version for this prompt — the same operation whether it's the
        newest draft or an older one (a rollback). Every sibling gets unpublished first so exactly
        one version is ever published per prompt at a time.
        """
        siblings = await self.list_by_prompt(prompt_id)
        for sibling in siblings:
            if sibling.id != version.id and sibling.is_published:
                sibling.is_published = False
                if sibling.status == PromptStatus.PUBLISHED:
                    sibling.status = PromptStatus.DEPRECATED
                await self.update(sibling)

        version.is_published = True
        version.status = PromptStatus.PUBLISHED
        return await self.update(version)
