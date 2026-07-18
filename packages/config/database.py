from __future__ import annotations

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    url: PostgresDsn = Field(alias="DATABASE_URL")

    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    echo: bool = False