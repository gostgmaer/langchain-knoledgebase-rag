# Schema auth
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RefreshTokenRequestSchema(BaseModel):
    """Incoming refresh-token request."""

    model_config = ConfigDict(
        extra="forbid",
    )

    refresh_token: str = Field(
        min_length=1,
        description="The refresh token issued by IAM at login.",
    )


class RefreshTokenResponseSchema(BaseModel):
    """A new access token (and possibly a rotated refresh token) from IAM."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    access_token: str

    refresh_token: str | None = None

    token_type: str

    expires_in: int
