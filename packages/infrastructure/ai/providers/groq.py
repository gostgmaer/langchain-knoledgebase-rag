# groq.py
from __future__ import annotations

from langchain_groq import ChatGroq

from packages.config.loader import settings
from packages.infrastructure.ai.exceptions import require_api_key

from .base_provider import BaseProvider


class GroqProvider(BaseProvider):

    def _create_model(self):
        api_key = require_api_key(
            settings.ai.groq_api_key,
            env_var="GROQ_API_KEY",
            provider="groq",
        )
        return ChatGroq(
            api_key=api_key,
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )