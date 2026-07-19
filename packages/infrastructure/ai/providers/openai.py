# openai.py
from langchain_openai import ChatOpenAI

from .base_provider import BaseProvider


class OpenAIProvider(BaseProvider):

    def _create_model(self):
        return ChatOpenAI(
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )