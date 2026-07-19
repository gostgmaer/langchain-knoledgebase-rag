from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.models.base import BaseModel

ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseRepository(Generic[ModelType]):
    """Generic async repository for SQLAlchemy models."""

    model: type[ModelType]

    def __init__(
        self,
        model: type[ModelType],
        session: AsyncSession,
    ) -> None:
        self.model = model
        self.session = session

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(
        self,
        entity: ModelType,
    ) -> ModelType:
        self.session.add(entity)
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get(
        self,
        entity_id: Any,
    ) -> ModelType | None:
        stmt = (
            select(self.model)
            .where(self.model.id == entity_id)
        )

        return await self.scalar(stmt)

    async def exists(
        self,
        entity_id: Any,
    ) -> bool:
        stmt = (
            select(func.count())
            .select_from(self.model)
            .where(self.model.id == entity_id)
        )

        count = await self.session.scalar(stmt)

        return bool(count)

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model)

        return int(await self.session.scalar(stmt) or 0)

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ModelType]:
        stmt = (
            select(self.model)
            .offset(offset)
            .limit(limit)
        )

        return await self.scalars(stmt)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update(
        self,
        entity: ModelType,
    ) -> ModelType:
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(
        self,
        entity: ModelType,
    ) -> None:
        await self.session.delete(entity)
        await self.session.commit()

    async def delete_by_id(
        self,
        entity_id: Any,
    ) -> bool:
        stmt = (
            delete(self.model)
            .where(self.model.id == entity_id)
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        return result.rowcount > 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def scalar(
        self,
        stmt: Select[Any],
    ) -> ModelType | None:
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def scalars(
        self,
        stmt: Select[Any],
    ) -> list[ModelType]:
        result = await self.session.execute(stmt)
        return list(result.scalars().all())