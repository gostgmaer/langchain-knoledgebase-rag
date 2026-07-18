from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .enums import StorageProvider


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    provider: StorageProvider = StorageProvider.LOCAL

    upload_directory: Path = Path("storage/uploads")

    temp_directory: Path = Path("storage/temp")

    max_file_size: int = Field(
        default=50 * 1024 * 1024
    )

    signed_url_expiry: int = 3600