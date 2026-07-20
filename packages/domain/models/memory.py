# Memory model
from __future__ import annotations

from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.config.loader import settings
from packages.domain.models.base import BaseModel
from packages.memory.schemas import MemoryType


class Memory(BaseModel):
    """
    A single piece of long-term AI memory (fact, preference, profile
    detail, task, or summary), embedded for semantic search.
    """

    __tablename__ = "memories"

    __table_args__ = (
        Index("ix_memory_tenant", "tenant_id"),
        Index("ix_memory_user", "user_id"),
        Index("ix_memory_conversation", "conversation_id"),
        Index("ix_memory_type", "type"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )

    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
    )

    conversation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
    )

    type: Mapped[MemoryType] = mapped_column(
        SAEnum(MemoryType),
        nullable=False,
        default=MemoryType.FACT,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    importance: Mapped[float] = mapped_column(
        Float,
        default=0.5,
        nullable=False,
    )

    vector: Mapped[list[float]] = mapped_column(
        Vector(settings.embedding.dimensions),
        nullable=False,
    )

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )
