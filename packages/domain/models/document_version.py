# Document version model
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.domain.models.base import BaseModel


class DocumentVersion(BaseModel):
    """
    One row per superseded-or-current Document row in a re-upload
    lineage. A document with no re-uploads has zero rows here — this
    table only exists once a second upload with changed content
    arrives for the same tenant/knowledge-base/filename. Old versions
    are never destroyed: `Document.is_current` flips to `False` and a
    new Document row is created, linked back here.
    """

    __tablename__ = "document_versions"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            name="uq_document_version_document",
        ),
        Index("ix_docver_root", "root_document_id"),
    )

    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    root_document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
