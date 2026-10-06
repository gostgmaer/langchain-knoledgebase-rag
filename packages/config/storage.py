from __future__ import annotations

from pathlib import Path

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

    # max_file_size moved to Platform Settings (docs/BUGS.md item 38 follow-up) — see
    # platform_settings_service.py's SETTINGS. signed_url_expiry was dead config (nothing read
    # it) and was removed outright.