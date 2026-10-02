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

    # Matches the real Upload Service's own default (docs/BUGS.md item 22) — confirmed live against
    # the actually-running service's source (its config/index.js: `maxFileSize: _int(process.env.
    # MAX_FILE_SIZE, 10485760)`) and its container env (no MAX_FILE_SIZE override set), not guessed
    # from a doc comment. A larger value here just means a doomed upload fails late (after reaching
    # this app) instead of failing the local check first — override via MAX_FILE_SIZE if the deployed
    # Upload Service is ever reconfigured with a higher limit of its own.
    max_file_size: int = Field(
        default=10 * 1024 * 1024
    )

    signed_url_expiry: int = 3600