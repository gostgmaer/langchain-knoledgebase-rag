from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from packages.config.loader import settings
from packages.shared.logging import get_logger

from .models import LLMProvider

if TYPE_CHECKING:
    from packages.domain.models.model_profile import ModelProfile

logger = get_logger(__name__)


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


def build_llm_config_from_profile(profile: ModelProfile) -> LLMConfig | None:
    """
    Builds an `LLMConfig` from a `ModelProfile` row — docs/BUGS.md item 15:
    a profile's `provider`/`model`/`temperature`/etc. used to be stored and
    shown in the admin UI but never actually read; `ai.manager`'s global
    default was silently used for every conversation regardless of which
    profile its agent was configured with.

    Returns None (caller falls back to the global default) rather than
    raising when the profile's provider isn't one `LLMFactory` actually
    implements — `ModelProvider` (the domain enum stored on profiles) has
    several values (MISTRAL, OLLAMA, OPENROUTER, FIREWORKS, TOGETHER,
    COHERE, CUSTOM) with no real provider class behind them yet; a profile
    naming one of those is a genuine, separate gap (building that provider
    integration), not something to paper over by crashing a chat request.
    """

    try:
        provider = LLMProvider(profile.provider.lower())
    except ValueError:
        logger.warning(
            "Model profile references a provider LLMFactory doesn't implement yet — "
            "falling back to the global default for this request",
            profile_id=str(profile.id),
            profile_provider=profile.provider,
        )
        return None

    return LLMConfig(
        provider=provider,
        model=profile.model,
        temperature=float(profile.temperature),
        max_tokens=profile.max_tokens,
        top_p=float(profile.top_p) if profile.top_p is not None else None,
        top_k=profile.top_k,
        streaming=True,
    )