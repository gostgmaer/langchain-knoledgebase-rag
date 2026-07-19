from __future__ import annotations

from packages.infrastructure.ai.config import LLMConfig
from packages.infrastructure.ai.models import LLMProvider
from packages.infrastructure.ai.base import BaseLLMProvider
from packages.infrastructure.ai.exceptions import InvalidProviderError

from .google import GoogleProvider
from .openai import OpenAIProvider
from .anthropic import AnthropicProvider
from .groq import GroqProvider


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
