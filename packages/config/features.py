from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class FeatureSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    enable_rag: bool = True

    enable_tools: bool = True

    enable_memory: bool = True

    enable_streaming: bool = True

    enable_reranking: bool = True

    enable_query_rewrite: bool = True

    enable_web_search: bool = True

    enable_weather: bool = True

    enable_news: bool = True

    enable_calculator: bool = True