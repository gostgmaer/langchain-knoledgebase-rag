from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete
from sqlalchemy import exists
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.models.document_chunk import DocumentChunk
from packages.infrastructure.repositories.base import BaseRepository


class DocumentChunkRepository(BaseRepository[DocumentChunk]):
    """Repository for document chunks."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        super().__init__(DocumentChunk, session)

    async def get(
        self,
        chunk_id: UUID,
    ) -> DocumentChunk | None:
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.id == chunk_id)
        )

        return await self.scalar(stmt)

    async def get_by_ids(
        self,
        chunk_ids: list[UUID],
    ) -> list[DocumentChunk]:
        if not chunk_ids:
            return []

        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.id.in_(chunk_ids))
            .order_by(DocumentChunk.chunk_index.asc())
        )

        return await self.scalars(stmt)

    async def list_by_document(
        self,
        document_id: UUID,
    ) -> list[DocumentChunk]:
        stmt = (
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
            )
            .order_by(
                DocumentChunk.chunk_index.asc(),
            )
        )

        return await self.scalars(stmt)

    async def list_by_tenant(
        self,
        tenant_id: UUID,
    ) -> list[DocumentChunk]:
        stmt = (
            select(DocumentChunk)
            .where(
                DocumentChunk.tenant_id == tenant_id,
            )
            .order_by(
                DocumentChunk.document_id.asc(),
                DocumentChunk.chunk_index.asc(),
            )
        )

        return await self.scalars(stmt)

    async def count_by_document(
        self,
        document_id: UUID,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
            )
        )

        return int(await self.session.scalar(stmt) or 0)

    async def count_by_tenant(
        self,
        tenant_id: UUID,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(DocumentChunk)
            .where(
                DocumentChunk.tenant_id == tenant_id,
            )
        )

        return int(await self.session.scalar(stmt) or 0)

    async def exists(
        self,
        chunk_id: UUID,
    ) -> bool:
        stmt = (
            select(
                exists().where(
                    DocumentChunk.id == chunk_id,
                )
            )
        )

        return bool(await self.session.scalar(stmt))

    async def delete_by_document(
        self,
        document_id: UUID,
    ) -> int:
        stmt = (
            delete(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
            )
        )

        result = await self.session.execute(stmt)

        return result.rowcount or 0

    async def delete_by_tenant(
        self,
        tenant_id: UUID,
    ) -> int:
        stmt = (
            delete(DocumentChunk)
            .where(
                DocumentChunk.tenant_id == tenant_id,
            )
        )

        result = await self.session.execute(stmt)

        return result.rowcount or 0