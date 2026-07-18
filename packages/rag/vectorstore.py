# Vector store implementation
from __future__ import annotations

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from langchain_chroma import Chroma
from langchain_postgres import PGVector

from packages.config.settings import settings
from packages.rag.embeddings import EmbeddingManager
from packages.rag.exceptions import VectorStoreException


class VectorStoreManager:
    """Manages vector store providers."""

    def __init__(
        self,
        embeddings: EmbeddingManager,
    ) -> None:
        self.provider = settings.vector_store_backend.lower()
        self.embeddings = embeddings

        self._store = self._create()

    def _create(self) -> VectorStore:

        if self.provider == "chroma":
            return Chroma(
                collection_name=settings.vector_collection_name,
                embedding_function=self.embeddings.client,
                persist_directory=settings.chroma_directory,
            )

        if self.provider == "pgvector":
            return PGVector(
                embeddings=self.embeddings.client,
                collection_name=settings.vector_collection_name,
                connection=settings.database_url,
            )

        raise VectorStoreException(
            f"Unsupported vector store: {self.provider}"
        )

    @property
    def client(self) -> VectorStore:
        return self._store

    async def add_documents(
        self,
        documents: list[Document],
    ) -> None:
        await self._store.aadd_documents(documents)

    async def similarity_search(
        self,
        query: str,
        *,
        k: int = 5,
    ) -> list[Document]:
        return await self._store.asimilarity_search(
            query,
            k=k,
        )

    async def delete(
        self,
        ids: list[str],
    ) -> None:
        await self._store.adelete(ids=ids)