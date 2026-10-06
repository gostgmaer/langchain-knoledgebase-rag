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

    # session_expiry_days moved to the database (docs/BUGS.md item 38) — an admin-configurable
    # Platform Setting now, not an env var; see platform_settings_service.py's SETTINGS registry
    # for its built-in default and packages/worker/jobs.py for how it's read per sweep.