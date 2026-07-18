# Prompt model
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    Index,
    String,
    Text,
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

from packages.domain.enums.prompt_category import PromptCategory
from packages.domain.models.base import BaseModel

if TYPE_CHECKING:
    from packages.domain.models.prompt_version import PromptVersion


class Prompt(BaseModel):
    """
    Logical prompt definition.

    The actual prompt text is stored in PromptVersion.

    Example:

    Support Prompt
        ├── v1
        ├── v2
        └── v3 (Published)

    Agents reference PromptVersion instead of Prompt
    so that every execution is reproducible.
    """

    __tablename__ = "prompts"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "slug",
            name="uq_prompt_slug",
        ),
        CheckConstraint(
            "length(name) > 0",
            name="ck_prompt_name",
        ),
        Index(
            "ix_prompt_tenant",
            "tenant_id",
        ),
        Index(
            "ix_prompt_slug",
            "slug",
        ),
        Index(
            "ix_prompt_category",
            "category",
        ),
        Index(
            "ix_prompt_active",
            "is_active",
        ),
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

    description: Mapped[str | None] = mapped_column(
        Text,
    )

    category: Mapped[PromptCategory] = mapped_column(
        Enum(PromptCategory),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
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

    versions: Mapped[list["PromptVersion"]] = relationship(
        back_populates="prompt",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PromptVersion.version.desc()",
    )

    @validates("name", "slug")
    def validate_required(
        self,
        key: str,
        value: str,
    ) -> str:
        value = value.strip()

        if not value:
            raise ValueError(f"{key} cannot be empty.")

        return value