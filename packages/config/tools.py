from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecuritySettings(BaseSettings):
    """Security configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    weather_api_key: str = Field(alias="OPENWEATHER_API_KEY")
    weather_api_url: str = Field(default="https://api.openweathermap.org", alias="OPENWEATHER_BASE_URL")
    news_api_key: str = Field(alias="NEWSAPI_API_KEY")
    news_api_url:str=Field(default="https://newsapi.org", alias="NEWSAPI_BASE_URL")
    serper_api_key:str=Field(default="", alias="SERPER_API_KEY")
    tavily_api_key:str=Field(default="", alias="TAVILY_API_KEY")