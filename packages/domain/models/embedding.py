from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.config.loader import settings
from packages.domain.models.base import BaseModel

if TYPE_CHECKING:
    from packages.domain.models.document_chunk import DocumentChunk
    from packages.domain.models.model_profile import ModelProfile


class Embedding(BaseModel):
    """Embedding vector for a document chunk."""

    __tablename__ = "embeddings"

    __table_args__ = (
        Index("ix_embedding_chunk", "chunk_id"),
        Index("ix_embedding_tenant", "tenant_id"),
        Index("ix_embedding_model_profile", "model_profile_id"),
        Index(
            "ix_embedding_vector",
            "vector",
            postgresql_using="hnsw",
            postgresql_ops={
                "vector": "vector_cosine_ops",
            },
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )

    chunk_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "document_chunks.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    model_profile_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "model_profiles.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    vector: Mapped[list[float]] = mapped_column(
        Vector(settings.embedding.dimensions),
        nullable=False,
    )

    chunk: Mapped["DocumentChunk"] = relationship(
        back_populates="embeddings",
        lazy="selectin",
    )

    model_profile: Mapped["ModelProfile"] = relationship(
        lazy="selectin",
    )