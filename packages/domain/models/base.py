# Base models
from __future__ import annotations

from packages.infrastructure.database.base import Base
from packages.infrastructure.database.mixins import (
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
)


class BaseModel(
    UUIDMixin,
    TimestampMixin,
    SoftDeleteMixin,
    Base,
):
    """Base model for all domain entities."""

    __abstract__ = True