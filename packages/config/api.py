from __future__ import annotations

from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class APISettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"

    api_prefix: str = "/api/v1"

    # The frontend/ Next.js app runs on a different origin (port) in
    # dev, so browser fetches need real CORS headers — see
    # packages/api/middleware/__init__.py. Comma-separated in .env.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"],
        alias="CORS_ORIGINS",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    # Production hardening's own "Rate limiting" gap — see
    # packages/api/middleware/rate_limit.py. Per-tenant (or per-IP
    # fallback) sliding window, requests per 60s. Default is generous
    # enough not to trip over normal dev/browser polling traffic (job
    # status polling, etc.) while still enforcing a real cap; 0 disables
    # it entirely.
    rate_limit_requests_per_minute: int = Field(
        default=300, alias="RATE_LIMIT_REQUESTS_PER_MINUTE"
    )