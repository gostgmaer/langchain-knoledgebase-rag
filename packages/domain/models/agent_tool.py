from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from packages.domain.models.base import BaseModel

if TYPE_CHECKING:
    from packages.domain.models.agent import Agent
    from packages.domain.models.tool import Tool


class AgentTool(BaseModel):
    """
    Per-agent tool configuration.
    """

    __tablename__ = "agent_tools"

    __table_args__ = (
        UniqueConstraint(
            "agent_id",
            "tool_id",
            name="uq_agent_tool",
        ),
        CheckConstraint(
            "priority >= 0",
            name="ck_agent_tool_priority",
        ),
        CheckConstraint(
            "timeout_seconds > 0",
            name="ck_agent_tool_timeout",
        ),
        CheckConstraint(
            "retry_count >= 0",
            name="ck_agent_tool_retry",
        ),
        Index("ix_agent_tool_agent", "agent_id"),
        Index("ix_agent_tool_tool", "tool_id"),
    )

    agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )

    tool_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tools.id", ondelete="RESTRICT"),
        nullable=False,
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
    )

    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
    )

    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )

    agent: Mapped["Agent"] = relationship(
        back_populates="tools",
    )

    tool: Mapped["Tool"] = relationship(
        back_populates="agent_tools",
        lazy="joined",
    )

    @validates("priority", "timeout_seconds", "retry_count")
    def validate_non_negative(self, key: str, value: int) -> int:
        if key == "timeout_seconds" and value <= 0:
            raise ValueError("timeout_seconds must be greater than 0.")
        if key != "timeout_seconds" and value < 0:
            raise ValueError(f"{key} cannot be negative.")
        return value