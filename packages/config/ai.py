from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    """AI provider configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )
    model: str = Field(default="gemini-3.1-flash-lite", alias="LLM_MODEL")

    google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")

    default_provider: str = Field(default="google", alias="LLM_PROVIDER")
    default_temperature: float = Field(default=0.2, alias="LLM_TEMPERATURE")
    max_tokens: int = Field(default=8192, alias="LLM_MAX_TOKENS")
    streaming: bool = Field(default=True, alias="LLM_STREAMING")
    top_p: float = Field(default=0.95, alias="LLM_TOP_P")
    top_k: int = Field(default=5, alias="LLM_TOP_K")

    circuit_breaker_failure_threshold: int = Field(default=5, alias="LLM_CIRCUIT_BREAKER_FAILURE_THRESHOLD")
    circuit_breaker_reset_seconds: float = Field(default=30.0, alias="LLM_CIRCUIT_BREAKER_RESET_SECONDS")