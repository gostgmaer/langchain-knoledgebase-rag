from __future__ import annotations

from pydantic import AnyHttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class IAMSettings(BaseSettings):
    """IAM service configuration."""

    model_config = SettingsConfigDict(
        env_prefix="IAM_",
        extra="ignore",
    )

    # Service
    base_url: AnyHttpUrl

    # Service-to-service authentication
    client_id: str
    client_secret: SecretStr

    # Session introspection
    introspection_api_key: SecretStr

    # HTTP
    timeout: float = 30.0

    verify_ssl: bool = True

    max_retries: int = 3
