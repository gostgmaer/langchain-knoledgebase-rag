from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.domain.models.base import BaseModel

if TYPE_CHECKING:
    from packages.domain.models.document_chunk import DocumentChunk


class Embedding(BaseModel):
    """Embedding vector for a document chunk."""

    __tablename__ = "embeddings"

    __table_args__ = (
        Index("ix_embedding_chunk", "chunk_id"),
    )

    chunk_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    dimensions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    vector: Mapped[list[float]] = mapped_column(
        Vector(),
        nullable=False,
    )

    chunk: Mapped["DocumentChunk"] = relationship(
        back_populates="embeddings",
    )