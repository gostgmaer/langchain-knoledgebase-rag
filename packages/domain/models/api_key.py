# API key model
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.domain.models.base import BaseModel


class ApiKey(BaseModel):
    """
    A tenant-scoped credential for programmatic access to this app's own API, independent of an
    IAM-issued browser session (docs/BUGS.md item 33). Resolves to a fixed "admin" role for its
    own tenant (packages/auth/service.py), attributed back to whoever created it
    (created_by_user_id/email) for audit purposes.

    The raw key is shown exactly once, at creation (packages/api/routers/api_keys.py) — only its
    SHA-256 hash is ever stored (packages/auth/api_keys.py), the same handling a password gets,
    not reversible even by someone with direct DB access. `key_prefix` is enough of the raw value
    to let an admin recognize which key is which in a list without ever re-exposing the secret.
    """

    __tablename__ = "api_keys"

    __table_args__ = (
        UniqueConstraint("key_hash", name="uq_api_key_hash"),
        Index("ix_api_key_tenant", "tenant_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    name: Mapped[str] = mapped_column(String(150), nullable=False)

    key_prefix: Mapped[str] = mapped_column(String(24), nullable=False)

    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    created_by_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    created_by_email: Mapped[str] = mapped_column(String(255), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
