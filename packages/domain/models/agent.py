# Agent model
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.domain.enums.agent_status import AgentStatus
from packages.domain.models.agent_prompt import AgentPrompt
from packages.domain.models.base import BaseModel

if TYPE_CHECKING:
    from packages.domain.models.agent_knowledge_base import AgentKnowledgeBase
    from packages.domain.models.agent_tool import AgentTool
    from packages.domain.models.conversation import Conversation


class Agent(BaseModel):
    """AI Agent."""

    __tablename__ = "agents"

    __table_args__ = (
        Index("ix_agent_tenant", "tenant_id"),
        Index("ix_agent_slug", "slug"),
        Index("ix_agent_status", "status"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(Text)

    system_prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    llm_provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    llm_model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    temperature: Mapped[float] = mapped_column(
        Numeric(3, 2),
        default=0.2,
        nullable=False,
    )

    top_p: Mapped[float] = mapped_column(
        Numeric(3, 2),
        default=0.95,
        nullable=False,
    )

    max_tokens: Mapped[int] = mapped_column(
        Integer,
        default=4096,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus),
        default=AgentStatus.ACTIVE,
        nullable=False,
    )

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )

    knowledge_bases: Mapped[list["AgentKnowledgeBase"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )

    tools: Mapped[list["AgentTool"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    model_profile_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "model_profiles.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    prompts: Mapped[list["AgentPrompt"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
