# Upload job model
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.domain.enums.upload_job_status import UploadJobStatus
from packages.domain.models.base import BaseModel


class UploadJob(BaseModel):
    """
    Tracks one document upload's async pipeline (queued -> running ->
    succeeded/failed) so a client can poll real progress instead of
    just blocking. Created at enqueue time (packages/api/routers/
    documents.py), before the Document row even exists — `document_id`
    starts `NULL` and is filled in once ingestion actually creates or
    finds one. `job_id` is the real arq job id when the queue is up;
    `NULL` when Redis was unreachable and the in-process fallback
    (`_ingest_in_background`) ran instead — both paths update the same
    row by its own primary key, not by `job_id`, so this stays
    populated correctly either way.
    """

    __tablename__ = "upload_jobs"

    __table_args__ = (
        Index("ix_upload_job_tenant", "tenant_id"),
        Index("ix_upload_job_status", "status"),
        Index("ix_upload_job_document", "document_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )

    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    job_id: Mapped[str | None] = mapped_column(
        String(64),
    )

    status: Mapped[UploadJobStatus] = mapped_column(
        Enum(UploadJobStatus),
        default=UploadJobStatus.QUEUED,
        nullable=False,
    )

    document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
    )

    error: Mapped[str | None] = mapped_column(Text)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
