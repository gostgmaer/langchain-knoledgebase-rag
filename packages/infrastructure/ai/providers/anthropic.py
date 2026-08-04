# anthropic.py
from __future__ import annotations

from langchain_anthropic import ChatAnthropic

from packages.config.loader import settings
from packages.infrastructure.ai.exceptions import require_api_key

from .base_provider import BaseProvider


class AnthropicProvider(BaseProvider):

    def _create_model(self):
        api_key = require_api_key(
            settings.ai.anthropic_api_key,
            env_var="ANTHROPIC_API_KEY",
            provider="anthropic",
        )
        return ChatAnthropic(
            api_key=api_key,
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )