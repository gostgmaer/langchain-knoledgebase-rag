from packages.config.loader import settings

from .registry import (
    AnthropicProvider,
    GoogleProvider,
    GroqProvider,
    OpenAIProvider,
)
from .base import BaseLLMProvider


class LLMFactory:

    @staticmethod
    def create() -> BaseLLMProvider:

        provider = settings.llm.provider.lower()

        if provider == "google":
            return GoogleProvider()

        if provider == "openai":
            return OpenAIProvider()

        if provider == "anthropic":
            return AnthropicProvider()

        if provider == "groq":
            return GroqProvider()

        raise ValueError(
            f"Unsupported LLM provider: {provider}"
        )