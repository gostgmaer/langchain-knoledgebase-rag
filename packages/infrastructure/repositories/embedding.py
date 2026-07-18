# Embedding repository
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.models.embedding import Embedding
from packages.infrastructure.repositories.base import BaseRepository


class EmbeddingRepository(BaseRepository[Embedding]):
    """Repository for Embedding metadata."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Embedding, session)

    async def list_by_document(
        self,
        document_id: UUID,
    ) -> list[Embedding]:
        stmt = (
            select(Embedding)
            .where(Embedding.document_id == document_id)
        )

        return await self.scalars(stmt)

    async def list_by_chunk(
        self,
        chunk_id: UUID,
    ) -> list[Embedding]:
        stmt = (
            select(Embedding)
            .where(Embedding.chunk_id == chunk_id)
        )

        return await self.scalars(stmt)

    async def count_by_document(
        self,
        document_id: UUID,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Embedding)
            .where(Embedding.document_id == document_id)
        )

        return int(await self.session.scalar(stmt) or 0)

    async def delete_by_document(
        self,
        document_id: UUID,
    ) -> int:
        embeddings = await self.list_by_document(document_id)

        for embedding in embeddings:
            await self.session.delete(embedding)

        return len(embeddings)