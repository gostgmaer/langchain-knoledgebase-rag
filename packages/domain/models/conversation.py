# Conversation model
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from packages.domain.enums.conversation_status import ConversationStatus
from packages.domain.models.base import BaseModel

if TYPE_CHECKING:
    from packages.domain.models.agent import Agent
    from packages.domain.models.message import Message


class Conversation(BaseModel):
    """
    Runtime conversation between a user and an AI agent.

    Stores immutable execution snapshots so historical
    conversations remain reproducible even if the
    agent configuration changes later.
    """

    __tablename__ = "conversations"

    __table_args__ = (
        CheckConstraint(
            "total_messages >= 0",
            name="ck_conversation_total_messages",
        ),
        CheckConstraint(
            "total_tokens >= 0",
            name="ck_conversation_total_tokens",
        ),
        CheckConstraint(
            "total_cost >= 0",
            name="ck_conversation_total_cost",
        ),
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ck_conversation_time_range",
        ),
        Index("ix_conversation_tenant", "tenant_id"),
        Index("ix_conversation_agent", "agent_id"),
        Index("ix_conversation_user", "user_id"),
        Index("ix_conversation_status", "status"),
        Index("ix_conversation_session", "session_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )

    agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=False,
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )

    session_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
    )

    title: Mapped[str | None] = mapped_column(
        String(255),
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
    )

    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus),
        default=ConversationStatus.ACTIVE,
        nullable=False,
    )

    # Runtime snapshots
    model_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    prompt_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    tool_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    retrieval_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    # Metrics
    total_messages: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    total_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    total_cost: Mapped[float] = mapped_column(
        default=0.0,
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        nullable=False,
    )

    last_message_at: Mapped[datetime | None]

    ended_at: Mapped[datetime | None]

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )

    # Relationships

    agent: Mapped["Agent"] = relationship(
        back_populates="conversations",
        lazy="joined",
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.created_at",
    )

    @validates("total_messages", "total_tokens")
    def validate_positive(
        self,
        key: str,
        value: int,
    ) -> int:
        if value < 0:
            raise ValueError(f"{key} cannot be negative.")
        return value

    @validates("total_cost")
    def validate_cost(
        self,
        _: str,
        value: float,
    ) -> float:
        if value < 0:
            raise ValueError("Cost cannot be negative.")
        return value
