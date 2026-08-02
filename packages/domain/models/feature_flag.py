# Feature flag model
from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.domain.models.base import BaseModel


class FeatureFlag(BaseModel):
    """
    A dynamic, no-redeploy-needed feature toggle (docs/mvpRAG.md v1.1)
    — replaces packages/config/features.py's static, env-driven
    FeatureSettings for the one flag that has a real runtime consumer
    (enable_rbac; the other 10 declared flags are inert config with no
    call site anywhere in this app).

    `tenant_id IS NULL` is the global default for `key`; a row with a
    real `tenant_id` overrides that default for just that tenant.
    """

    __tablename__ = "feature_flags"

    __table_args__ = (
        UniqueConstraint("key", "tenant_id", name="uq_feature_flag_key_tenant"),
    )

    key: Mapped[str] = mapped_column(String(100), nullable=False)

    tenant_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    description: Mapped[str | None] = mapped_column(String(500))
