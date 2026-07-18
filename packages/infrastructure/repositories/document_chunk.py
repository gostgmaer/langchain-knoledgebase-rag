from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.models.document_chunk import DocumentChunk
from packages.infrastructure.repositories.base import BaseRepository


class DocumentChunkRepository(BaseRepository[DocumentChunk]):
    """Repository for DocumentChunk entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(DocumentChunk, session)

    async def list_by_document(
        self,
        document_id: UUID,
        *,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[DocumentChunk]:
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
            .offset(offset)
            .limit(limit)
        )

        return await self.scalars(stmt)

    async def get_chunk(
        self,
        chunk_id: UUID,
    ) -> DocumentChunk | None:
        return await self.get(chunk_id)

    async def count_by_document(
        self,
        document_id: UUID,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
        )

        return int(await self.session.scalar(stmt) or 0)

    async def delete_by_document(
        self,
        document_id: UUID,
    ) -> int:
        chunks = await self.list_by_document(
            document_id,
            limit=100000,
        )

        for chunk in chunks:
            await self.session.delete(chunk)

        return len(chunks)