# google.py
from langchain_google_genai import ChatGoogleGenerativeAI

from packages.config.loader import settings
from packages.infrastructure.ai.exceptions import require_api_key

from .base_provider import BaseProvider


class GoogleProvider(BaseProvider):

    def _create_model(self):
        api_key = require_api_key(
            settings.ai.google_api_key,
            env_var="GOOGLE_API_KEY",
            provider="google",
        )
        return ChatGoogleGenerativeAI(
            model=self.config.model,
            api_key=api_key,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            top_p=self.config.top_p,
            top_k=self.config.top_k,
        )