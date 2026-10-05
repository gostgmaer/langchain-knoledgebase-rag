# Schema api key
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateApiKeyRequestSchema(BaseModel):
    """Incoming request to mint a new API key."""

    model_config = ConfigDict(
        extra="forbid",
    )

    name: str = Field(min_length=1, max_length=150)

    expires_at: datetime | None = None


class CreateApiKeyResponseSchema(BaseModel):
    """
    Returned exactly once, at creation — `key` is the real, usable secret. It is never stored
    (only its hash is) and never returned by any other endpoint; losing it means generating a new
    key, not recovering this one.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    name: str
    key: str
    key_prefix: str
    expires_at: datetime | None
    created_at: datetime


class ApiKeyResponseSchema(BaseModel):
    """A masked view for listing — never includes the raw key or its hash."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    name: str
    key_prefix: str
    is_active: bool
    created_by_email: str
    last_used_at: datetime | None
    expires_at: datetime | None
    created_at: datetime


class ApiKeyListResponseSchema(BaseModel):
    """Every API key this tenant has ever created, active or revoked."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    api_keys: list[ApiKeyResponseSchema]
