from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    name: str = Field(default="EasyDev AI Platform", alias="APP_NAME")
    version: str = Field(default="1.0.0", alias="APP_VERSION")
    environment: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")

    # Cleanup Jobs completion (docs/mvpRAG.md v1.1) — an ACTIVE
    # conversation with no activity for this long is swept as expired.
    session_expiry_days: int = Field(default=30, alias="SESSION_EXPIRY_DAYS")