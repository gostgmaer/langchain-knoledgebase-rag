from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
    validates,
)

from packages.domain.enums.agent_prompt_role import AgentPromptRole
from packages.domain.models.base import BaseModel

if TYPE_CHECKING:
    from packages.domain.models.agent import Agent
    from packages.domain.models.prompt_version import PromptVersion


class AgentPrompt(BaseModel):
    """
    Associates an Agent with a specific PromptVersion.

    Allows different prompt roles (SYSTEM, RAG, SAFETY, etc.)
    to evolve independently while preserving reproducibility.
    """

    __tablename__ = "agent_prompts"

    __table_args__ = (
        UniqueConstraint(
            "agent_id",
            "role",
            name="uq_agent_prompt_role",
        ),
        CheckConstraint(
            "priority >= 0",
            name="ck_agent_prompt_priority",
        ),
        Index("ix_agent_prompt_agent", "agent_id"),
        Index("ix_agent_prompt_role", "role"),
        Index("ix_agent_prompt_version", "prompt_version_id"),
    )

    agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "agents.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    prompt_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "prompt_versions.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    role: Mapped[AgentPromptRole] = mapped_column(
        Enum(AgentPromptRole),
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

    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Role-specific overrides and configuration.",
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

    agent: Mapped["Agent"] = relationship(
        back_populates="prompts",
    )

    prompt_version: Mapped["PromptVersion"] = relationship(
        lazy="joined",
    )

    #
    # Validation
    #

    @validates("priority")
    def validate_priority(
        self,
        _: str,
        value: int,
    ) -> int:
        if value < 0:
            raise ValueError("Priority cannot be negative.")
        return value