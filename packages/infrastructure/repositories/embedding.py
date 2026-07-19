from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.models.embedding import Embedding
from packages.infrastructure.repositories.base import BaseRepository


class EmbeddingRepository(BaseRepository[Embedding]):
    """Repository for Embedding entities."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        super().__init__(Embedding, session)

    async def list_by_chunk(
        self,
        chunk_id: UUID,
    ) -> list[Embedding]:
        stmt = select(Embedding).where(Embedding.chunk_id == chunk_id)

        return await self.scalars(stmt)

    async def get_by_chunk(
        self,
        chunk_id: UUID,
    ) -> Embedding | None:
        stmt = select(Embedding).where(Embedding.chunk_id == chunk_id).limit(1)

        return await self.scalar(stmt)

    async def count_by_chunk(
        self,
        chunk_id: UUID,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Embedding)
            .where(Embedding.chunk_id == chunk_id)
        )

        return int(await self.session.scalar(stmt) or 0)

    async def delete_by_chunk(
        self,
        chunk_id: UUID,
    ) -> int:
        embeddings = await self.list_by_chunk(chunk_id)

        for embedding in embeddings:
            await self.session.delete(embedding)

        return len(embeddings)

    async def get_by_chunk(
        self,
        chunk_id: UUID,
    ) -> Embedding | None:
        stmt = select(Embedding).where(Embedding.chunk_id == chunk_id).limit(1)

        return await self.scalar(stmt)

    async def list_by_chunk(
        self,
        chunk_id: UUID,
    ) -> list[Embedding]:
        stmt = select(Embedding).where(Embedding.chunk_id == chunk_id)

        return await self.scalars(stmt)

    async def list_by_model(
        self,
        model_profile_id: UUID,
    ) -> list[Embedding]:
        stmt = select(Embedding).where(
            Embedding.model_profile_id == model_profile_id,
        )

        return await self.scalars(stmt)

    async def count_by_chunk(
        self,
        chunk_id: UUID,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Embedding)
            .where(
                Embedding.chunk_id == chunk_id,
            )
        )

        return int(await self.session.scalar(stmt) or 0)

    async def count_by_tenant(
        self,
        tenant_id: UUID,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Embedding)
            .where(
                Embedding.tenant_id == tenant_id,
            )
        )

        return int(await self.session.scalar(stmt) or 0)

    async def exists_for_chunk(
        self,
        chunk_id: UUID,
    ) -> bool:
        stmt = select(
            exists().where(
                Embedding.chunk_id == chunk_id,
            )
        )

        return bool(await self.session.scalar(stmt))

    async def update_vector(
        self,
        chunk_id: UUID,
        vector: list[float],
    ) -> None:
        stmt = (
            update(Embedding)
            .where(
                Embedding.chunk_id == chunk_id,
            )
            .values(
                vector=vector,
            )
        )

        await self.session.execute(stmt)

    async def delete_by_chunk(
        self,
        chunk_id: UUID,
    ) -> int:
        stmt = delete(Embedding).where(
            Embedding.chunk_id == chunk_id,
        )

        result = await self.session.execute(stmt)

        return result.rowcount or 0

    async def delete_by_model(
        self,
        model_profile_id: UUID,
    ) -> int:
        stmt = delete(Embedding).where(
            Embedding.model_profile_id == model_profile_id,
        )

        result = await self.session.execute(stmt)

        return result.rowcount or 0

    async def delete_by_tenant(
        self,
        tenant_id: UUID,
    ) -> int:
        stmt = delete(Embedding).where(
            Embedding.tenant_id == tenant_id,
        )

        result = await self.session.execute(stmt)

        return result.rowcount or 0
