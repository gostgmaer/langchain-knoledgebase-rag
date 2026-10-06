# Schema platform settings
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class PlatformSettingItemSchema(BaseModel):
    """One operational knob: its description, current effective value, and whether that value
    is an admin override or still the `.env` default."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    label: str
    kind: str
    """int | bool | string_list"""
    help: str | None
    minimum: float | None
    maximum: float | None
    value: Any
    """The effective value in use right now."""
    env_default: Any
    is_overridden: bool


class PlatformSettingsResponseSchema(BaseModel):
    settings: list[PlatformSettingItemSchema]


class PlatformSettingsUpdateSchema(BaseModel):
    """
    Partial update, keyed by setting key — e.g. `{"rate_limit_requests_per_minute": 500}`. A key
    mapped to `null` reverts that one setting to its `.env` default; a key simply omitted is left
    untouched (unlike RetrievalSettingsUpdateSchema's PUT-replaces-everything shape, since there
    are many more keys here and an admin is far more likely to change one at a time).
    """

    model_config = ConfigDict(extra="forbid")

    values: dict[str, Any]
