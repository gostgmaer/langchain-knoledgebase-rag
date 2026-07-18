# Tool model
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from packages.domain.enums.tool_category import ToolCategory
from packages.domain.enums.tool_status import ToolStatus
from packages.domain.models.base import BaseModel

if TYPE_CHECKING:
    from packages.domain.models.agent_tool import AgentTool


class Tool(BaseModel):
    """Reusable tool definition."""

    __tablename__ = "tools"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "slug",
            name="uq_tool_slug",
        ),
        CheckConstraint(
            "timeout_seconds > 0",
            name="ck_tool_timeout",
        ),
        CheckConstraint(
            "retry_count >= 0",
            name="ck_tool_retry",
        ),
        Index("ix_tool_tenant", "tenant_id"),
        Index("ix_tool_category", "category"),
        Index("ix_tool_status", "status"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(Text)

    category: Mapped[ToolCategory] = mapped_column(
        Enum(ToolCategory),
        nullable=False,
    )

    provider: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
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

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    status: Mapped[ToolStatus] = mapped_column(
        Enum(ToolStatus),
        default=ToolStatus.ACTIVE,
        nullable=False,
    )

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )

    agent_tools: Mapped[list["AgentTool"]] = relationship(
        back_populates="tool",
        cascade="all, delete-orphan",
    )

    @validates("name", "slug")
    def validate_string(self, key: str, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError(f"{key} cannot be empty.")
        return value