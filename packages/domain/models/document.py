# Document model
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    BIGINT,
    JSON,
    Boolean,
    DateTime,
    Integer,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.domain.enums.document_status import DocumentStatus
from packages.domain.models.base import BaseModel

if TYPE_CHECKING:
    from packages.domain.models.document_chunk import DocumentChunk
    from packages.domain.models.knowledge_base import KnowledgeBase


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

    # --- Provenance / processing record. Structured columns (not JSON) because they are
    # filtered, joined and reported on. NULL means "not recorded" (documents ingested before
    # these existed) - never a guess.
    uploaded_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    source_type: Mapped[str | None] = mapped_column(String(32))
    processing_version: Mapped[str | None] = mapped_column(String(64))
    parser_name: Mapped[str | None] = mapped_column(String(64))
    chunking_strategy: Mapped[str | None] = mapped_column(String(32))
    chunking_version: Mapped[str | None] = mapped_column(String(32))
    embedding_provider: Mapped[str | None] = mapped_column(String(64))
    embedding_model: Mapped[str | None] = mapped_column(String(128))
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer)
    processing_stage: Mapped[str | None] = mapped_column(String(32))

    # --- External source provenance (NULL for uploaded documents). `source_type` above holds the
    # connector type ("upload", "web", "confluence", ...); these identify the exact external item.
    source_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    external_id: Mapped[str | None] = mapped_column(String(1024))
    canonical_url: Mapped[str | None] = mapped_column(Text)
    external_version: Mapped[str | None] = mapped_column(String(256))
    external_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))

    # --- Classification and access. `visibility`: NULL/"tenant" = every member of the tenant may
    # retrieve it; "restricted" = administrators only. Enforced inside the retrieval SQL.
    visibility: Mapped[str | None] = mapped_column(String(16))
    # For "restricted" documents: besides administrators, members holding one of these role names,
    # or listed by user id, may retrieve it. Both NULL/empty = administrators only.
    allowed_roles: Mapped[list[str] | None] = mapped_column(JSONB)
    allowed_users: Mapped[list[str] | None] = mapped_column(JSONB)
    document_type: Mapped[str | None] = mapped_column(String(64))
    category: Mapped[str | None] = mapped_column(String(64))
    tags: Mapped[list[str] | None] = mapped_column(JSONB)
    """Last pipeline stage reached: extracting, cleaning, chunking, embedding, indexing, completed."""
    error_reason: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )

    knowledge_base: Mapped[KnowledgeBase] = relationship(
        back_populates="documents",
    )

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
