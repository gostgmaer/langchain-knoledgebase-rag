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

from packages.domain.enums.prompt_status import PromptStatus
from packages.domain.models.base import BaseModel

if TYPE_CHECKING:
    from packages.domain.models.prompt import Prompt


class PromptVersion(BaseModel):
    """
    Immutable version of a prompt template.

    Agents should reference PromptVersion rather than Prompt to
    ensure conversations remain reproducible.
    """

    __tablename__ = "prompt_versions"

    __table_args__ = (
        UniqueConstraint(
            "prompt_id",
            "version",
            name="uq_prompt_version",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_prompt_version_positive",
        ),
        CheckConstraint(
            "length(template) > 0",
            name="ck_prompt_template_not_empty",
        ),
        Index(
            "ix_prompt_version_prompt",
            "prompt_id",
        ),
        Index(
            "ix_prompt_version_status",
            "status",
        ),
        Index(
            "ix_prompt_version_published",
            "is_published",
        ),
    )

    prompt_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "prompts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[PromptStatus] = mapped_column(
        Enum(PromptStatus),
        default=PromptStatus.DRAFT,
        nullable=False,
    )

    template: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    variables: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Template variables with optional metadata.",
    )

    examples: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="Few-shot examples.",
    )

    changelog: Mapped[str | None] = mapped_column(
        Text,
    )

    is_published: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
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

    prompt: Mapped["Prompt"] = relationship(
        back_populates="versions",
        lazy="joined",
    )

    #
    # Validation
    #

    @validates("version")
    def validate_version(
        self,
        _: str,
        value: int,
    ) -> int:
        if value < 1:
            raise ValueError("Version must be at least 1.")
        return value

    @validates("template")
    def validate_template(
        self,
        _: str,
        value: str,
    ) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Prompt template cannot be empty.")

        return value