# Retrieval settings model
from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, Float, Index, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.domain.models.base import BaseModel


class RetrievalSettings(BaseModel):
    """
    Per-tenant overrides of how retrieval behaves. One row per tenant; a NULL column means "use the
    platform default" (the environment value), so a tenant only stores what it changed.
    """

    __tablename__ = "retrieval_settings"

    __table_args__ = (Index("uq_retrieval_settings_tenant", "tenant_id", unique=True),)

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    max_results: Mapped[int | None] = mapped_column(Integer)
    min_relevance_score: Mapped[float | None] = mapped_column(Float)
    reranking_enabled: Mapped[bool | None] = mapped_column(Boolean)
    updated_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
