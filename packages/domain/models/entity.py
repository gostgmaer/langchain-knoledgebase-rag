# Knowledge graph entity model
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.domain.models.base import BaseModel


class Entity(BaseModel):
    """A knowledge-graph entity extracted from ingested documents, scoped
    tenant-wide (not per-knowledge-base) since SearchFilter — the only
    thing GraphRAGRetriever has to query with — has no knowledge_base_id
    field."""

    __tablename__ = "entities"

    __table_args__ = (
        Index("ix_entity_tenant", "tenant_id"),
        UniqueConstraint(
            "tenant_id",
            "name_lower",
            "entity_type",
            name="uq_entity_tenant_name_type",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    name_lower: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Plain column, not sqlalchemy.Enum — entity_type is LLM-derived and
    # open-ended, same reasoning as DocumentChunk.section. A native
    # Postgres enum here would hit the same drift bug this project has
    # already been bitten by once (MemoryType needed a hand-run
    # ALTER TYPE ... ADD VALUE; create_all() never retrofits it).
    entity_type: Mapped[str | None] = mapped_column(
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )
