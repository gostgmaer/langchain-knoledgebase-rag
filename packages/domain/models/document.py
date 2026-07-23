# Document model
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    BIGINT,
    JSON,
    Boolean,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.domain.enums.document_status import DocumentStatus
from packages.domain.models.base import BaseModel

if TYPE_CHECKING:
    from packages.domain.models.knowledge_base import KnowledgeBase
    from packages.domain.models.document_chunk import DocumentChunk


class Document(BaseModel):
    """Knowledge base document."""

    __tablename__ = "documents"

    __table_args__ = (
        Index("ix_document_kb", "knowledge_base_id"),
        Index("ix_document_status", "status"),
        Index("ix_document_file", "file_id"),
    )

    knowledge_base_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(Text)

    # The Upload Service's own file ID (packages/sdk/upload/) — a Mongo
    # ObjectId string against the real service, not a UUID, so this
    # can't be a UUID column even though every other *_id column here is.
    file_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    extension: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    size_bytes: Mapped[int] = mapped_column(
        BIGINT,
        nullable=False,
    )

    checksum: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    language: Mapped[str | None] = mapped_column(
        String(20),
    )

    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus),
        default=DocumentStatus.PENDING,
        nullable=False,
    )

    # True for whichever Document row is the live version of this
    # tenant/knowledge-base/filename lineage. Flips to False the
    # moment a re-upload with changed content creates a new row —
    # see packages/domain/models/document_version.py.
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )

    knowledge_base: Mapped["KnowledgeBase"] = relationship(
        back_populates="documents",
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
