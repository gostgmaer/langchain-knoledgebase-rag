from __future__ import annotations

from uuid import UUID


from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.domain.models.agent import Agent
from packages.domain.models.base import BaseModel
from packages.domain.models.knowledge_base import KnowledgeBase


class AgentKnowledgeBase(BaseModel):
    """Maps agents to knowledge bases."""

    __tablename__ = "agent_knowledge_bases"

    __table_args__ = (
        UniqueConstraint(
            "agent_id",
            "knowledge_base_id",
            name="uq_agent_kb",
        ),
    )

    agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )

    knowledge_base_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent: Mapped["Agent"] = relationship(
        back_populates="knowledge_bases",
    )

    knowledge_base: Mapped["KnowledgeBase"] = relationship(
        back_populates="agent_links",
    )
