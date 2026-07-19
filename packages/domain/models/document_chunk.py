# Document chunk model
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.domain.models.base import BaseModel

if TYPE_CHECKING:
    from packages.domain.models.document import Document
    from packages.domain.models.embedding import Embedding


class DocumentChunk(BaseModel):
    """Represents a chunk of a document."""

    __tablename__ = "document_chunks"

    __table_args__ = (
        Index("ix_chunk_document", "document_id"),
        Index("ix_chunk_tenant", "tenant_id"),
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunk_index",
        ),
        CheckConstraint(
            "chunk_index >= 0",
            name="ck_chunk_index_positive",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    page_number: Mapped[int | None] = mapped_column(
        Integer,
    )

    section: Mapped[str | None] = mapped_column(
        nullable=True,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    character_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    start_offset: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    end_offset: Mapped[int | None] = mapped_column(
        Integer,
    )

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )

    document: Mapped["Document"] = relationship(
        back_populates="chunks",
    )
    source: Mapped[str | None]
    embeddings: Mapped[list["Embedding"]] = relationship(
        back_populates="chunk",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
