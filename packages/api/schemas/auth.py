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


class CurrentUserResponseSchema(BaseModel):
    """
    The calling user's profile — first_name/last_name specifically, which the access token's own
    JWT claims don't carry (confirmed live: a decoded token has sub/email/tenantId/roles/etc, no
    name fields), so a frontend building its session purely from local JWT decoding (the fast,
    no-network-call path `GET /api/auth/session` uses on every page load) has no way to show a
    real name instead of falling back to the raw email. This endpoint costs nothing extra beyond
    what already happens: `request.state.current_user` is already resolved from IAM's own real
    `GET /auth/me` by the authentication middleware on every authenticated request — this just
    returns it, meant to be called once at login/refresh rather than on every page load.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: str
    email: str
    first_name: str | None = None
    last_name: str | None = None
