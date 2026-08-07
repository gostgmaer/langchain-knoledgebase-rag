# Knowledge graph relationship (edge) model
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.domain.models.base import BaseModel


class Relationship(BaseModel):
    """A directed edge between two Entity rows, first-seen in one
    document. Provenance is deliberately single-document (an MVP cut,
    no multi-document evidence tracking) — a relationship re-extracted
    from a second document reuses the same edge via get_or_create rather
    than recording a second source."""

    __tablename__ = "relationships"

    __table_args__ = (
        Index("ix_relationship_tenant", "tenant_id"),
        Index("ix_relationship_source", "source_entity_id"),
        Index("ix_relationship_target", "target_entity_id"),
        UniqueConstraint(
            "source_entity_id",
            "target_entity_id",
            "relationship_type",
            name="uq_relationship_edge",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )

    source_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
    )

    target_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Plain column, not sqlalchemy.Enum — same open-ended/LLM-derived
    # reasoning as Entity.entity_type.
    relationship_type: Mapped[str | None] = mapped_column(
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )
