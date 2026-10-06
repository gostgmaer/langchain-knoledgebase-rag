# Platform setting model
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.domain.models.base import BaseModel


class PlatformSetting(BaseModel):
    """
    A platform-wide operational knob an admin changed away from its `.env` default — rate
    limits, CORS origins, retention windows, and the like (docs/BUGS.md item 38). Not a
    per-tenant thing like RetrievalSettings/FeatureFlag; one row per key, platform-wide, same
    reasoning as this being config an *operator* tunes, not something a tenant customizes.

    No row for a key means "use the `.env`/`packages/config/` default" — this table only ever
    holds the keys someone actually changed, same "NULL/absent = platform default" idiom as
    RetrievalSettings. `value` is JSONB so one table serves every settings's type (int, bool,
    list[str]) without a column per type or a migration per new setting; `packages/application/
    services/platform_settings_service.py`'s `SETTINGS` registry is the single source of truth
    for which keys exist, their type, and their validation range.
    """

    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    value: Mapped[Any] = mapped_column(JSONB, nullable=False)

    updated_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
