from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING


from sqlalchemy import (
    UUID,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.domain.models.base import BaseModel

if TYPE_CHECKING:
    from packages.domain.models.document import Document
    from packages.domain.models.document_chunk import DocumentChunk
    from packages.domain.models.message import Message


class MessageCitation(BaseModel):
    """
    Citation attached to an assistant message.

    Represents one retrieved chunk used to generate
    an answer.
    """

    __tablename__ = "message_citations"

    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "chunk_id",
            name="uq_message_chunk",
        ),
        CheckConstraint(
            "score >= 0",
            name="ck_citation_score",
        ),
        CheckConstraint(
            "rank >= 1",
            name="ck_citation_rank",
        ),
        Index("ix_citation_message", "message_id"),
        Index("ix_citation_document", "document_id"),
        Index("ix_citation_chunk", "chunk_id"),
    )

    message_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )

    document_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    chunk_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
    )

    rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    score: Mapped[Decimal] = mapped_column(
        Numeric(8, 6),
        nullable=False,
    )

    message: Mapped["Message"] = relationship(
        back_populates="citations",
    )

    document: Mapped["Document"] = relationship()

    chunk: Mapped["DocumentChunk"] = relationship()