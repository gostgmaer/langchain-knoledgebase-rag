# Feedback model
from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Enum,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.domain.enums.feedback_rating import FeedbackRating
from packages.domain.models.base import BaseModel

if TYPE_CHECKING:
    from packages.domain.models.message import Message


class Feedback(BaseModel):
    """
    A user's thumbs-up/down (plus optional comment) on one assistant
    message. One user can leave at most one feedback row per message —
    resubmitting updates it rather than creating a duplicate.
    """

    __tablename__ = "feedback"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "message_id",
            name="uq_feedback_user_message",
        ),
        Index("ix_feedback_tenant", "tenant_id"),
        Index("ix_feedback_message", "message_id"),
        Index("ix_feedback_rating", "rating"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )

    message_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )

    rating: Mapped[FeedbackRating] = mapped_column(
        Enum(FeedbackRating),
        nullable=False,
    )

    comment: Mapped[str | None] = mapped_column(Text)

    message: Mapped["Message"] = relationship()
