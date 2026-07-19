from __future__ import annotations

from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, validates

from packages.config.loader import settings
from packages.domain.enums.model_provider import ModelProvider
from packages.domain.enums.model_status import ModelStatus
from packages.domain.models.base import BaseModel


class ModelProfile(BaseModel):
    """
    Reusable LLM configuration.

    Multiple agents can reference the same profile.
    """

    __tablename__ = "model_profiles"

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "model",
            name="uq_model_profile_provider_model",
        ),
        CheckConstraint(
            "temperature >= 0 AND temperature <= 2",
            name="ck_model_temperature",
        ),
        CheckConstraint(
            "top_p > 0 AND top_p <= 1",
            name="ck_model_top_p",
        ),
        CheckConstraint(
            "max_tokens > 0",
            name="ck_model_max_tokens",
        ),
        CheckConstraint(
            "context_window > 0",
            name="ck_model_context_window",
        ),
        CheckConstraint(
            "embedding_dimensions >= 0",
            name="ck_model_embedding_dimensions",
        ),
        Index("ix_model_provider", "provider"),
        Index("ix_model_status", "status"),
        Index("ix_model_name", "model"),
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Friendly profile name",
    )

    provider: Mapped[ModelProvider] = mapped_column(
        Enum(ModelProvider),
        nullable=False,
    )

    model: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
    )

    temperature: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        default=Decimal("0.20"),
        nullable=False,
    )

    top_p: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        default=Decimal("0.95"),
        nullable=False,
    )

    top_k: Mapped[int | None] = mapped_column(
        Integer,
    )

    max_tokens: Mapped[int] = mapped_column(
        Integer,
        default=4096,
        nullable=False,
    )

    context_window: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    embedding_dimensions: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    vector: Mapped[list[float]] = mapped_column(
        Vector(settings.embedding.dimensions),
        nullable=False,
    )

    supports_streaming: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    supports_tools: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    supports_reasoning: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    supports_images: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    supports_embeddings: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    status: Mapped[ModelStatus] = mapped_column(
        Enum(ModelStatus),
        default=ModelStatus.ACTIVE,
        nullable=False,
    )

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )

    @validates("temperature")
    def validate_temperature(
        self,
        _: str,
        value: Decimal,
    ) -> Decimal:
        if not Decimal("0") <= value <= Decimal("2"):
            raise ValueError("Temperature must be between 0 and 2.")
        return value

    @validates("top_p")
    def validate_top_p(
        self,
        _: str,
        value: Decimal,
    ) -> Decimal:
        if not Decimal("0") < value <= Decimal("1"):
            raise ValueError("top_p must be between 0 and 1.")
        return value

    @validates("max_tokens", "context_window")
    def validate_positive(
        self,
        field: str,
        value: int,
    ) -> int:
        if value <= 0:
            raise ValueError(f"{field} must be greater than zero.")
        return value
