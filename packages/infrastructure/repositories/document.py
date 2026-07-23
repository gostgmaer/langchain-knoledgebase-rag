# Document repository
# Document chunk repository
from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.domain.models.document import Document
from packages.infrastructure.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    """Repository for Document entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Document, session)

    async def get_by_filename(
        self,
        filename: str,
    ) -> Document | None:
        """Return a document by filename."""
        stmt = (
            select(Document)
            .where(Document.file_name == filename)
        )

        return await self.scalar(stmt)

    async def get_by_checksum(
        self,
        knowledge_base_id: UUID,
        checksum: str,
    ) -> Document | None:
        """
        Return a document by content checksum, scoped to a knowledge
        base. Used to detect a re-upload of unchanged content so
        ingestion can skip re-embedding it.
        """
        stmt = (
            select(Document)
            .where(
                Document.knowledge_base_id == knowledge_base_id,
                Document.checksum == checksum,
            )
        )

        return await self.scalar(stmt)

    async def get_current_by_tenant_kb_and_filename(
        self,
        tenant_id: UUID,
        knowledge_base_id: UUID,
        file_name: str,
    ) -> Document | None:
        """
        Return the live version of a document lineage — the one
        Document row with `is_current=True` for this tenant/knowledge
        base/filename. Used by the ingestion pipeline to detect a
        re-upload with *changed* content (a checksum miss against an
        existing filename), distinct from a brand-new document.
        """
        stmt = (
            select(Document)
            .where(
                Document.tenant_id == tenant_id,
                Document.knowledge_base_id == knowledge_base_id,
                Document.file_name == file_name,
                Document.is_current.is_(True),
            )
        )

        return await self.scalar(stmt)

    async def list_by_knowledge_base(
        self,
        knowledge_base_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Document]:
        """Return all documents belonging to a knowledge base."""
        stmt = (
            select(Document)
            .where(Document.knowledge_base_id == knowledge_base_id)
            .order_by(desc(Document.created_at))
            .offset(offset)
            .limit(limit)
        )

        return await self.scalars(stmt)

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Document]:
        """
        Return all documents belonging to a tenant, across every
        knowledge base it owns — unlike `list_by_knowledge_base`, which
        only existed for the ingestion pipeline's own per-KB needs.
        """
        stmt = (
            select(Document)
            .where(Document.tenant_id == tenant_id)
            .order_by(desc(Document.created_at))
            .offset(offset)
            .limit(limit)
        )

        return await self.scalars(stmt)

    async def count_by_tenant(
        self,
        tenant_id: UUID,
    ) -> int:
        """Count documents belonging to a tenant, across every knowledge base."""
        stmt = (
            select(func.count())
            .select_from(Document)
            .where(Document.tenant_id == tenant_id)
        )

        return int(await self.session.scalar(stmt) or 0)

    async def get_with_chunks(
        self,
        document_id: UUID,
    ) -> Document | None:
        """Return document with all chunks."""
        stmt = (
            select(Document)
            .options(selectinload(Document.chunks))
            .where(Document.id == document_id)
        )

        return await self.scalar(stmt)

    async def count_by_knowledge_base(
        self,
        knowledge_base_id: UUID,
    ) -> int:
        """Count documents in a knowledge base."""
        stmt = (
            select(func.count())
            .select_from(Document)
            .where(
                Document.knowledge_base_id == knowledge_base_id
            )
        )

        return int(await self.session.scalar(stmt) or 0)

    async def update_status(
        self,
        document: Document,
        status: str,
    ) -> Document:
        """Update document processing status."""
        document.status = status

        await self.session.flush()
        await self.session.refresh(document)

        return document