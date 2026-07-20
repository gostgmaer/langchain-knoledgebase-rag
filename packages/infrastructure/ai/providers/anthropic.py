# anthropic.py
from __future__ import annotations

from langchain_anthropic import ChatAnthropic

from packages.config.loader import settings

from .base_provider import BaseProvider


class AnthropicProvider(BaseProvider):

    def _create_model(self):
        return ChatAnthropic(
            api_key=settings.ai.anthropic_api_key,
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )