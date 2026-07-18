# Message model
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
    validates,
)

from packages.domain.enums.finish_reason import FinishReason
from packages.domain.enums.message_role import MessageRole
from packages.domain.enums.message_status import MessageStatus
from packages.domain.models.base import BaseModel

if TYPE_CHECKING:
    from packages.domain.models.conversation import Conversation
    from packages.domain.models.message import Message
    from packages.domain.models.message_citation import MessageCitation


class Message(BaseModel):
    """
    Represents one message within a conversation.
    """

    __tablename__ = "messages"

    __table_args__ = (
        CheckConstraint(
            "prompt_tokens >= 0",
            name="ck_msg_prompt_tokens",
        ),
        CheckConstraint(
            "completion_tokens >= 0",
            name="ck_msg_completion_tokens",
        ),
        CheckConstraint(
            "total_tokens >= 0",
            name="ck_msg_total_tokens",
        ),
        CheckConstraint(
            "latency_ms >= 0",
            name="ck_msg_latency",
        ),
        CheckConstraint(
            "cost >= 0",
            name="ck_msg_cost",
        ),
        Index("ix_msg_conversation", "conversation_id"),
        Index("ix_msg_role", "role"),
        Index("ix_msg_status", "status"),
        Index("ix_msg_parent", "parent_message_id"),
    )

    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )

    parent_message_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
    )

    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole),
        nullable=False,
    )

    status: Mapped[MessageStatus] = mapped_column(
        Enum(MessageStatus),
        default=MessageStatus.COMPLETED,
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    #
    # Tool execution
    #

    tool_calls: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    tool_results: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    #
    # AI execution metadata
    #

    reasoning_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    retrieval_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    guardrail_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    usage_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    #
    # Metrics
    #

    prompt_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    completion_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    total_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    latency_ms: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        default=Decimal("0"),
        nullable=False,
    )

    finish_reason: Mapped[FinishReason | None] = mapped_column(
        Enum(FinishReason),
    )

    model_name: Mapped[str | None] = mapped_column(
        String(100),
    )

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )

    #
    # Relationships
    #

    conversation: Mapped["Conversation"] = relationship(
        back_populates="messages",
    )

    parent: Mapped["Message | None"] = relationship(
        remote_side="Message.id",
        back_populates="children",
    )

    children: Mapped[list["Message"]] = relationship(
        back_populates="parent",
    )

    citations: Mapped[list["MessageCitation"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
    )

    @validates(
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "latency_ms",
    )
    def validate_positive(
        self,
        key: str,
        value: int,
    ) -> int:
        if value < 0:
            raise ValueError(f"{key} cannot be negative.")
        return value

    @validates("cost")
    def validate_cost(
        self,
        _: str,
        value: Decimal,
    ) -> Decimal:
        if value < 0:
            raise ValueError("Cost cannot be negative.")
        return value
