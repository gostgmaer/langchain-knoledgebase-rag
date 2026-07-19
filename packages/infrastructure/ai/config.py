from __future__ import annotations

from dataclasses import dataclass

from packages.config.loader import settings

from .models import LLMProvider


@dataclass(slots=True, frozen=True)
class LLMConfig:
    """
    Runtime configuration for a language model.
    """

    provider: LLMProvider
    model: str

    temperature: float
    max_tokens: int

    top_p: float | None = None
    top_k: int | None = None

    streaming: bool = True


def get_default_llm_config() -> LLMConfig:
    """
    Returns the default LLM configuration from application settings.
    """

    return LLMConfig(
        provider=LLMProvider(settings.ai.default_provider),
        model=settings.ai.model,
        temperature=settings.ai.default_temperature,
        max_tokens=settings.ai.max_tokens,
        top_p=settings.ai.top_p,
        top_k=settings.ai.top_k,
        streaming=True,
    )