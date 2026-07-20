from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EmbeddingSettings(BaseSettings):
    """Embedding model configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )
    model: str = Field(default="gemini-pro", alias="LLM_MODEL")

    dimensions: int | None = Field(default=3072, alias="EMBEDDING_DIMENSIONS")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")

    default_provider: str = Field(default="google", alias="LLM_PROVIDER")
    default_temperature: float = Field(default=0.2, alias="LLM_TEMPERATURE")
    max_tokens: int = Field(default=8192, alias="LLM_MAX_TOKENS")
    streaming: bool = Field(default=True, alias="LLM_STREAMING")