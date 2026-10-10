from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.enums.model_status import ModelStatus
from packages.domain.models.model_profile import ModelProfile
from packages.infrastructure.repositories.base import BaseRepository


class ModelProfileRepository(BaseRepository[ModelProfile]):
    """Repository for AI model profiles."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        super().__init__(ModelProfile, session)

    async def clear_default(self) -> None:
        """
        Unsets `is_default` on every profile. Callers run this immediately before marking a
        profile as the new default, inside the same request-scoped transaction, so exactly one
        profile ever has `is_default=True` — nothing previously enforced that invariant (not a
        unique constraint, not application logic), so two profiles could each be "the" default at
        once, and `get_default()`'s `.limit(1)` with no deterministic ordering would silently pick
        either one each time it's called (docs/BUGS.md item 39).
        """
        await self.session.execute(update(ModelProfile).values(is_default=False))

    async def get_by_name(
        self,
        name: str,
    ) -> ModelProfile | None:
        stmt = select(ModelProfile).where(
            func.lower(ModelProfile.name) == name.lower(),
        )

        return await self.scalar(stmt)

    async def get_default(
        self,
    ) -> ModelProfile | None:
        stmt = (
            select(ModelProfile)
            .where(
                ModelProfile.is_default.is_(True),
                ModelProfile.status == ModelStatus.ACTIVE,
            )
            .limit(1)
        )

        return await self.scalar(stmt)

    async def list_active(
        self,
    ) -> list[ModelProfile]:
        stmt = (
            select(ModelProfile)
            .where(
                ModelProfile.status == ModelStatus.ACTIVE,
            )
            .order_by(ModelProfile.name.asc())
        )

        return await self.scalars(stmt)

    async def list_embedding_models(
        self,
    ) -> list[ModelProfile]:
        stmt = (
            select(ModelProfile)
            .where(
                ModelProfile.status == ModelStatus.ACTIVE,
                ModelProfile.supports_embeddings.is_(True),
            )
            .order_by(ModelProfile.name.asc())
        )

        return await self.scalars(stmt)

    async def list_chat_models(
        self,
    ) -> list[ModelProfile]:
        stmt = (
            select(ModelProfile)
            .where(
                ModelProfile.status == ModelStatus.ACTIVE,
                ModelProfile.supports_embeddings.is_(False),
            )
            .order_by(ModelProfile.name.asc())
        )

        return await self.scalars(stmt)
