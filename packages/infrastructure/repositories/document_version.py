# Document version repository
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.models.document_version import DocumentVersion
from packages.infrastructure.repositories.base import BaseRepository


class DocumentVersionRepository(BaseRepository[DocumentVersion]):
    """Repository for DocumentVersion entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(DocumentVersion, session)

    async def get_by_document(
        self,
        document_id: UUID,
    ) -> DocumentVersion | None:
        stmt = select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
        )

        return await self.scalar(stmt)

    async def list_by_root(
        self,
        root_document_id: UUID,
    ) -> list[DocumentVersion]:
        stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.root_document_id == root_document_id)
            .order_by(DocumentVersion.version_number.asc())
        )

        return await self.scalars(stmt)

    async def max_version_number(
        self,
        root_document_id: UUID,
    ) -> int:
        stmt = select(func.max(DocumentVersion.version_number)).where(
            DocumentVersion.root_document_id == root_document_id,
        )

        return int(await self.session.scalar(stmt) or 0)

    async def mark_superseded(
        self,
        version: DocumentVersion,
    ) -> DocumentVersion:
        version.superseded_at = datetime.now(UTC)

        return await self.update(version)
