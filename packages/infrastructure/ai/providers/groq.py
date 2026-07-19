# groq.py
from __future__ import annotations

from langchain_groq import ChatGroq

from .base_provider import BaseProvider


class GroqProvider(BaseProvider):

    def _create_model(self):
        return ChatGroq(
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )