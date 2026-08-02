from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ObservabilitySettings(BaseSettings):
    """LangSmith tracing configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    tracing_enabled: bool = Field(default=False, alias="LANGCHAIN_TRACING_V2")
    endpoint: str = Field(default="https://api.smith.langchain.com", alias="LANGCHAIN_ENDPOINT")
    api_key: str | None = Field(default=None, alias="LANGCHAIN_API_KEY")
    project: str = Field(default="default", alias="LANGCHAIN_PROJECT")

    # OpenTelemetry (docs/mvpRAG.md v1.1) — a distinct tracing path
    # from LangSmith above: OTel is standard distributed tracing across
    # the whole request (HTTP -> graph nodes -> outbound calls), not
    # just LLM/chain calls. Off by default — needs a real OTLP
    # collector (e.g. Jaeger, see docker-compose.yml's `jaeger`
    # service) to actually be useful.
    otel_enabled: bool = Field(default=False, alias="OTEL_ENABLED")
    otel_endpoint: str = Field(default="localhost:4317", alias="OTEL_ENDPOINT")
    otel_service_name: str = Field(default="easydev-ai-platform", alias="OTEL_SERVICE_NAME")

    @property
    def active(self) -> bool:
        """Whether tracing should actually be turned on.

        Requires both the flag and a real key — `tracing_enabled=true`
        with no key would otherwise send every LangChain/LangGraph call
        through a tracer that immediately fails to authenticate.
        """

        return self.tracing_enabled and bool(self.api_key)


def configure_langsmith(settings: ObservabilitySettings) -> bool:
    """
    Bridges this app's typed config into the real process environment.

    LangChain/LangGraph's tracing is driven entirely by `LANGCHAIN_*`/
    `LANGSMITH_*` env vars read directly by `langsmith`/`langchain-core`
    at call time — not through this app's own settings objects. This is
    the one place that's allowed to touch `os.environ` directly, since
    it's bridging our config layer into a third-party SDK's global
    env-var contract, not scattering ad-hoc `os.getenv()` calls through
    business logic.

    Returns whether tracing was actually enabled.
    """

    if not settings.active:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        return False

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = settings.endpoint
    os.environ["LANGCHAIN_API_KEY"] = settings.api_key or ""
    os.environ["LANGCHAIN_PROJECT"] = settings.project
    return True
