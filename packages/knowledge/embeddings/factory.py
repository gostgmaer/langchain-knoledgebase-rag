"""
Embedding provider factory.
"""

from __future__ import annotations

from packages.config.loader import settings

from .base import EmbeddingProvider
from .exceptions import UnsupportedEmbeddingProviderError
from .google import GoogleEmbeddingProvider
from .ollama import OllamaEmbeddingProvider
from .openai import OpenAIEmbeddingProvider


class EmbeddingFactory:
    """Creates embedding providers."""

    @staticmethod
    def create() -> EmbeddingProvider:

        provider = settings.rag.embedding_provider.lower()

        match provider:

            case "google":
                return GoogleEmbeddingProvider()

            case "openai":
                return OpenAIEmbeddingProvider()

            case "ollama":
                return OllamaEmbeddingProvider()

            case _:
                raise UnsupportedEmbeddingProviderError(
                    f"Unsupported embedding provider: {provider}"
                )