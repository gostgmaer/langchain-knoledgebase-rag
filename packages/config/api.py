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

    # The frontend/ Next.js app runs on a different origin (port) in
    # dev, so browser fetches need real CORS headers — see
    # packages/api/middleware/__init__.py. Comma-separated in .env.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"],
        alias="CORS_ORIGINS",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

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

    # Production hardening's own "Rate limiting" gap — see
    # packages/api/middleware/rate_limit.py. Per-tenant (or per-IP
    # fallback) sliding window, requests per 60s. Default is generous
    # enough not to trip over normal dev/browser polling traffic (job
    # status polling, etc.) while still enforcing a real cap; 0 disables
    # it entirely.
    rate_limit_requests_per_minute: int = Field(
        default=300, alias="RATE_LIMIT_REQUESTS_PER_MINUTE"
    )