from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisSettings(BaseSettings):
    """Redis configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    url: str = Field(alias="REDIS_URL")

    default_ttl: int = 3600