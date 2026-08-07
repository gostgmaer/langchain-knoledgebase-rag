# Knowledge graph entity-to-document provenance model
from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.domain.models.base import BaseModel


class EntityMention(BaseModel):
    """Links an Entity to a document it was extracted from.
    Document-level, not chunk-level: extraction runs once per document
    on a concatenated excerpt, so chunk-level provenance would be
    fabricated precision."""

    __tablename__ = "entity_mentions"

    __table_args__ = (
        Index("ix_entity_mention_entity", "entity_id"),
        Index("ix_entity_mention_document", "document_id"),
        UniqueConstraint(
            "entity_id",
            "document_id",
            name="uq_entity_mention",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )

    entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
