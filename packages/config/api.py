from __future__ import annotations

from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class APISettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"

    api_prefix: str = "/api/v1"

    # cors_origins moved to the database (docs/BUGS.md item 38) — it's an admin-configurable
    # Platform Setting now, not an env var; see packages/application/services/
    # platform_settings_service.py's SETTINGS registry for its built-in default and
    # packages/api/middleware/cors.py's DynamicCORSMiddleware for how it's read per request.

    # Real IAM enforcement. Off (default): the legacy fail-open behaviour -
    # anonymous callers get the default tenant, a rejected token is ignored.
    # On: every route except the public ones (health, docs, token refresh)
    # needs a valid IAM bearer token, a rejected token is a 401, an
    # unreachable IAM is a 503, and admin-only routes check the caller's roles.
    auth_required: bool = Field(default=False, alias="AUTH_REQUIRED")

    admin_roles: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["super_admin", "admin", "tenant_admin"],
        alias="ADMIN_ROLES",
    )

    @field_validator("admin_roles", mode="before")
    @classmethod
    def _split_roles(cls, value: object) -> object:
        if isinstance(value, str):
            return [role.strip() for role in value.split(",") if role.strip()]
        return value

    # Roles allowed to act on behalf of ANOTHER tenant by sending X-Tenant-ID
    # (the platform operator's "browse as tenant" feature). For everyone else
    # the tenant always comes from the verified token.
    tenant_override_roles: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["super_admin"],
        alias="TENANT_OVERRIDE_ROLES",
    )

    @field_validator("tenant_override_roles", mode="before")
    @classmethod
    def _split_override_roles(cls, value: object) -> object:
        if isinstance(value, str):
            return [role.strip() for role in value.split(",") if role.strip()]
        return value

    # Refuse verified-token requests from accounts whose email IAM has not
    # verified (403). Off by default; turn on together with IAM's
    # registration email verification for anything internet-facing.
    require_verified_email: bool = Field(default=False, alias="REQUIRE_VERIFIED_EMAIL")

    # rate_limit_requests_per_minute / rate_limit_expensive_requests_per_minute also moved to the
    # database (docs/BUGS.md item 38) — see packages/api/middleware/rate_limit.py (now reads
    # through PlatformSettingsService on every request) and platform_settings_service.py's
    # SETTINGS registry for their built-in defaults.