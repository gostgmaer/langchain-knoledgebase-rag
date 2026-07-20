# openai.py
from langchain_openai import ChatOpenAI

from packages.config.loader import settings

from .base_provider import BaseProvider


class OpenAIProvider(BaseProvider):

    def _create_model(self):
        return ChatOpenAI(
            api_key=settings.ai.openai_api_key,
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )