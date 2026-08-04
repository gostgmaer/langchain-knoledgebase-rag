# openai.py
from langchain_openai import ChatOpenAI

from packages.config.loader import settings
from packages.infrastructure.ai.exceptions import require_api_key

from .base_provider import BaseProvider


class OpenAIProvider(BaseProvider):

    def _create_model(self):
        api_key = require_api_key(
            settings.ai.openai_api_key,
            env_var="OPENAI_API_KEY",
            provider="openai",
        )
        return ChatOpenAI(
            api_key=api_key,
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )