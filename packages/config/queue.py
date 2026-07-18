from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class QueueSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    prefix: str = Field(default="easydev", alias="QUEUE_PREFIX")

    concurrency: int = 5

    max_retries: int = 3

    retry_delay: int = 5