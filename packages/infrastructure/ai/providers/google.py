# google.py
from langchain_google_genai import ChatGoogleGenerativeAI

from .base_provider import BaseProvider
from packages.config.loader import settings

class GoogleProvider(BaseProvider):

    def _create_model(self):
        return ChatGoogleGenerativeAI(
            model=self.config.model,
            api_key=settings.ai.google_api_key,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            top_p=self.config.top_p,
            top_k=self.config.top_k,
        )