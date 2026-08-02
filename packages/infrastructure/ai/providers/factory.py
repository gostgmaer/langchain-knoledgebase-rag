from __future__ import annotations

from packages.infrastructure.ai.base import BaseLLMProvider
from packages.infrastructure.ai.config import LLMConfig
from packages.infrastructure.ai.exceptions import InvalidProviderError
from packages.infrastructure.ai.models import LLMProvider

from .anthropic import AnthropicProvider
from .google import GoogleProvider
from .groq import GroqProvider
from .openai import OpenAIProvider


class LLMFactory:

    @staticmethod
    def create(config: LLMConfig) -> BaseLLMProvider:

        match config.provider:

            case LLMProvider.GOOGLE:
                return GoogleProvider(config)

            case LLMProvider.OPENAI:
                return OpenAIProvider(config)

            case LLMProvider.ANTHROPIC:
                return AnthropicProvider(config)

            case LLMProvider.GROQ:
                return GroqProvider(config)

            case _:
                raise InvalidProviderError(f"Unsupported provider: {config.provider}")
