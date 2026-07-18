from __future__ import annotations

from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings

from packages.config.loader import settings
from packages.rag.exceptions import EmbeddingException


class EmbeddingManager:
    """Manages embedding providers."""

    def __init__(self) -> None:
        self.provider = settings.embedding_provider.lower()
        self.model = settings.embedding_model
        self._embeddings = self._create()

    def _create(self) -> Embeddings:
        """Create embedding provider."""

        if self.provider == "google":
            return GoogleGenerativeAIEmbeddings(
                model=self.model,
                google_api_key=settings.google_api_key,
            )

        if self.provider == "openai":
            return OpenAIEmbeddings(
                model=self.model,
                api_key=settings.openai_api_key,
            )

        raise EmbeddingException(
            f"Unsupported embedding provider: {self.provider}"
        )

    @property
    def client(self) -> Embeddings:
        return self._embeddings

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        return self._embeddings.embed_query(text)

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        return self._embeddings.embed_documents(texts)