from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    url: str = Field(alias="DATABASE_URL")

    # Create/upgrade tables when the API starts (needs a role that owns the tables). Turn OFF when the
    # application connects as an ordinary least-privilege role and migrations are run separately with
    # `alembic upgrade head` (see docs/PROVENANCE.md).
    schema_init_at_startup: bool = Field(default=True, alias="SCHEMA_INIT_AT_STARTUP")

    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    echo: bool = False