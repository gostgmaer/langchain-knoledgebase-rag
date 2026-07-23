# AI response model
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.domain.models.base import BaseModel


class AIResponse(BaseModel):
    """
    A raw snapshot of what the LLM provider actually returned for one
    assistant turn — `response_metadata`/`additional_kwargs`/
    `usage_metadata` straight off the LangChain message object, before
    any of this app's own normalization. Separate from `Message`
    (the display-facing, already-cleaned row): useful for evaluation/
    audit when a provider's raw output needs inspecting independent of
    what got shown to the user.
    """

    __tablename__ = "ai_responses"

    __table_args__ = (
        UniqueConstraint(
            "message_id",
            name="uq_ai_response_message",
        ),
        Index("ix_ai_response_message", "message_id"),
    )

    message_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    model: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    raw_response: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    message = relationship("Message")
