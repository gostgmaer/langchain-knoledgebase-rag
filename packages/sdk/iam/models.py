from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ServiceToken(BaseModel):
    """
    `POST /auth/token` (client_credentials) response — confirmed live
    against https://iam.easydev.in that the envelope/camelCase pattern
    matches INTEGRATION_GUIDE.md's own example (`data.accessToken`,
    `data.expiresIn`); `tokenType` itself wasn't visible in a captured
    success response (no valid credentials to test with yet), so it
    defaults rather than being required.
    """

    model_config = ConfigDict(populate_by_name=True)

    access_token: str = Field(alias="accessToken")

    token_type: str = Field(default="Bearer", alias="tokenType")

    expires_in: int = Field(alias="expiresIn")


class CurrentUser(BaseModel):
    """
    `GET /auth/me` — confirmed live against https://iam.easydev.in with
    a real access token (a super_admin session). `roles`/`permissions`
    are plain string codes (e.g. `"super_admin"`, `"user:read"`,
    confirmed with ~140 real permission codes in the actual response)
    — **not** nested `{id, name, code}` objects, which is what this
    model originally (wrongly) assumed.

    `id` uses `AliasChoices("id", "sub")`: `/auth/me`'s HTTP response
    calls it `id`, but a raw decoded JWT payload (e.g. if this model
    is ever built from token claims directly instead of the HTTP
    response) calls the same value `sub` — confirmed both conventions
    are real by decoding an actual token side-by-side with the /auth/me
    call it authenticated. `session_id`/`two_factor_passed` are JWT-only
    claims, absent from `/auth/me`'s own response body — confirmed
    live, hence optional here rather than required.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: UUID = Field(validation_alias=AliasChoices("id", "sub"))

    tenant_id: UUID = Field(alias="tenantId")

    tenant_slug: str | None = Field(default=None, alias="tenantSlug")

    email: str

    first_name: str | None = Field(default=None, alias="firstName")

    last_name: str | None = Field(default=None, alias="lastName")

    is_active: bool | None = Field(default=None, alias="isActive")

    is_super_admin: bool | None = Field(default=None, alias="isSuperAdmin")

    roles: list[str] = Field(default_factory=list)

    permissions: list[str] = Field(default_factory=list)

    session_id: UUID | None = Field(default=None, alias="sessionId")

    two_factor_passed: bool | None = Field(default=None, alias="twoFactorPassed")


class IntrospectionResponse(BaseModel):
    """
    `POST /auth/introspect` — confirmed live that this endpoint is
    real (401 "Invalid or expired API key" with a placeholder key, not
    404), but the success shape itself is inferred from the same
    claims convention as `CurrentUser` above, not yet confirmed live
    with a valid `x-api-key`. Fields beyond `active` are optional so a
    partially-wrong guess here doesn't crash parsing.
    """

    model_config = ConfigDict(populate_by_name=True)

    active: bool

    session_id: UUID | None = Field(default=None, alias="sessionId")

    user_id: UUID | None = Field(default=None, alias="userId")

    tenant_id: UUID | None = Field(default=None, alias="tenantId")

    roles: list[str] = Field(default_factory=list)

    permissions: list[str] = Field(default_factory=list)


class User(BaseModel):
    """
    `GET /users/:id` — field names inferred from this service's
    consistent camelCase convention (confirmed live elsewhere: JWKS,
    openid-configuration, JWT claims), not yet verified live itself
    since nothing in this app currently calls `IAMUsersSDK.get_user()`.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: UUID

    tenant_id: UUID = Field(alias="tenantId")

    email: str

    first_name: str | None = Field(default=None, alias="firstName")

    last_name: str | None = Field(default=None, alias="lastName")

    is_active: bool = Field(default=True, alias="isActive")

    is_verified: bool = Field(default=False, alias="isVerified")

    created_at: datetime = Field(alias="createdAt")

    updated_at: datetime = Field(alias="updatedAt")


class Tenant(BaseModel):
    """
    `GET /tenants/:id` — same caveat as `User` above: inferred
    camelCase convention, not yet live-verified, unused elsewhere in
    this app today.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: UUID

    name: str

    slug: str

    is_active: bool = Field(default=True, alias="isActive")
