from __future__ import annotations

from pydantic import AnyHttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class NotificationSettings(BaseSettings):
    """Notification service configuration."""

    model_config = SettingsConfigDict(
        env_prefix="NOTIFICATION_",
        extra="ignore",
    )

    base_url: AnyHttpUrl

    api_key: SecretStr

    timeout: float = 30.0

    verify_ssl: bool = True