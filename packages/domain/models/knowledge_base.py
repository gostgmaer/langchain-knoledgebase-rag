# Knowledge base model
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Enum,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.domain.enums.knowledge_base_status import (
    KnowledgeBaseStatus,
)
from packages.domain.enums.search_type import SearchType
from packages.domain.enums.similarity_metric import (
    SimilarityMetric,
)
from packages.domain.models.agent_knowledge_base import AgentKnowledgeBase
from packages.domain.models.base import BaseModel

if TYPE_CHECKING:
    from packages.domain.models.document import Document


class KnowledgeBase(BaseModel):
    """Knowledge Base."""

    __tablename__ = "knowledge_bases"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "slug",
            name="uq_kb_tenant_slug",
        ),
        Index("ix_kb_tenant", "tenant_id"),
        Index("ix_kb_status", "status"),
        Index("ix_kb_slug", "slug"),
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

    description: Mapped[str | None] = mapped_column(
        Text,
    )

    status: Mapped[KnowledgeBaseStatus] = mapped_column(
        Enum(KnowledgeBaseStatus),
        default=KnowledgeBaseStatus.ACTIVE,
        nullable=False,
    )

    embedding_provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    embedding_model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    embedding_dimension: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    chunk_size: Mapped[int] = mapped_column(
        Integer,
        default=1000,
    )

    chunk_overlap: Mapped[int] = mapped_column(
        Integer,
        default=200,
    )

    similarity_metric: Mapped[SimilarityMetric] = mapped_column(
        Enum(SimilarityMetric),
        default=SimilarityMetric.COSINE,
        nullable=False,
    )

    search_type: Mapped[SearchType] = mapped_column(
        Enum(SearchType),
        default=SearchType.SIMILARITY,
        nullable=False,
    )

    max_results: Mapped[int] = mapped_column(
        Integer,
        default=10,
    )

    required_permission: Mapped[str | None] = mapped_column(
        String(255),
    )

    is_public: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
    )
    agent_links: Mapped[list["AgentKnowledgeBase"]] = relationship(
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
    )

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )
