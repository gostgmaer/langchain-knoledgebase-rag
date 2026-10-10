from __future__ import annotations

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class UploadServiceSettings(BaseSettings):
    """Configuration for the EasyDev Upload Service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    base_url: AnyHttpUrl = Field(
        alias="UPLOAD_SERVICE_URL",
        description="Base URL of the Upload Service",
    )

    api_key: str | None = Field(
        default=None,
        alias="UPLOAD_SERVICE_API_KEY",
        description="Optional service-to-service API key",
    )

    # The Upload Service (GATEWAY_AUTH_REQUIRED=true, its default) only
    # accepts requests carrying an X-Gateway-Hmac signature made with this
    # shared secret - the same value as its GATEWAY_INTERNAL_SECRET /
    # FILE_UPLOAD_HMAC_SECRET. Unset = no signature is sent (only works
    # against an Upload Service running with GATEWAY_AUTH_REQUIRED=false).
    hmac_secret: str | None = Field(
        default=None,
        alias="FILE_UPLOAD_HMAC_SECRET",
        description="Shared secret used to sign requests to the Upload Service",
    )

    # RAG is a trusted backend acting for its own already-authorised
    # tenants (tenant scoping is the X-Tenant-Id header), so it presents a
    # service-level role. Valid values in the Upload Service: user | admin.
    service_role: str = Field(
        default="admin",
        alias="UPLOAD_SERVICE_ROLE",
        description="Role presented to the Upload Service in the signed identity",
    )