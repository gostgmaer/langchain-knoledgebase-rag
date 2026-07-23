# Upload job repository
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.enums.upload_job_status import UploadJobStatus
from packages.domain.models.upload_job import UploadJob
from packages.infrastructure.repositories.base import BaseRepository


class UploadJobRepository(BaseRepository[UploadJob]):
    """Repository for UploadJob entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(UploadJob, session)

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[UploadJob]:
        stmt = (
            select(UploadJob)
            .where(UploadJob.tenant_id == tenant_id)
            .order_by(desc(UploadJob.created_at))
            .offset(offset)
            .limit(limit)
        )

        return await self.scalars(stmt)

    async def count_by_tenant(
        self,
        tenant_id: UUID,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(UploadJob)
            .where(UploadJob.tenant_id == tenant_id)
        )

        return int(await self.session.scalar(stmt) or 0)

    async def mark_running(
        self,
        job: UploadJob,
    ) -> UploadJob:
        job.status = UploadJobStatus.RUNNING
        job.started_at = datetime.now(UTC)

        return await self.update(job)

    async def mark_succeeded(
        self,
        job: UploadJob,
        document_id: UUID,
    ) -> UploadJob:
        job.status = UploadJobStatus.SUCCEEDED
        job.document_id = document_id
        job.finished_at = datetime.now(UTC)

        return await self.update(job)

    async def mark_failed(
        self,
        job: UploadJob,
        error: str,
    ) -> UploadJob:
        job.status = UploadJobStatus.FAILED
        job.error = error
        job.finished_at = datetime.now(UTC)

        return await self.update(job)
