from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

import chromadb

from packages.config.loader import settings
from packages.knowledge.vectorstores.base import BaseVectorStore
from packages.knowledge.vectorstores.providers.chroma import ChromaVectorStore
from packages.knowledge.vectorstores.providers.pgvector import PostgresVectorStore



class VectorStoreFactory:

    @staticmethod
    def create(
        *,
        session: AsyncSession,
        chroma_client: chromadb.ClientAPI | None = None,
    ) -> BaseVectorStore:

        provider = settings.vector_store_provider.lower()

        if provider == "postgres":
            return PostgresVectorStore(
                session=session,
            )

        if provider == "chroma":
            if chroma_client is None:
                raise ValueError(
                    "Chroma client is required."
                )

            return ChromaVectorStore(
                client=chroma_client,
                collection_name=settings.chroma_collection,
            )

        raise ValueError(
            f"Unsupported vector store provider: {provider}"
        )