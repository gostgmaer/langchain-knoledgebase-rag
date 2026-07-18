from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LoggingSettings(BaseSettings):
    """Logging configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    level: str = Field(default="INFO", alias="LOG_LEVEL")

    json_logs: bool = Field(default=False, alias="LOG_JSON")