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

    timeout: int = Field(
        default=30,
        alias="UPLOAD_SERVICE_TIMEOUT",
        ge=1,
        le=300,
        description="Request timeout in seconds",
    )

    api_key: str | None = Field(
        default=None,
        alias="UPLOAD_SERVICE_API_KEY",
        description="Optional service-to-service API key",
    )

    signed_url_expiry: int = Field(
        default=3600,
        alias="UPLOAD_SIGNED_URL_EXPIRY",
        ge=60,
        description="Default signed URL expiry in seconds",
    )

    verify_ssl: bool = Field(
        default=True,
        alias="UPLOAD_SERVICE_VERIFY_SSL",
    )