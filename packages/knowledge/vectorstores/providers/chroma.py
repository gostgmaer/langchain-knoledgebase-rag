# chroma.py - Future
from __future__ import annotations

from uuid import UUID

import chromadb
from chromadb.api.models.Collection import Collection

from packages.domain.models.embedding import Embedding
from packages.knowledge.vectorstores.base import BaseVectorStore
from packages.knowledge.vectorstores.schema import (
    SearchFilter,
    SearchOptions,
    SearchResult,
)


class ChromaVectorStore(BaseVectorStore):
    """
    ChromaDB Vector Store implementation.
    """

    def __init__(
        self,
        client: chromadb.ClientAPI,
        collection_name: str,
    ) -> None:

        self.client = client

        self.collection: Collection = (
            self.client.get_or_create_collection(
                name=collection_name,
                metadata={
                    "hnsw:space": "cosine",
                },
            )
        )

    async def similarity_search(
        self,
        query_embedding: Embedding,
        *,
        filters: SearchFilter,
        options: SearchOptions | None = None,
    ) -> list[SearchResult]:

        options = options or SearchOptions()

        where: dict[str, object] = {
            "tenant_id": str(filters.tenant_id),
            "model_profile_id": str(filters.model_profile_id),
        }

        if filters.document_id:
            where["document_id"] = str(filters.document_id)

        if filters.metadata:
            where.update(filters.metadata)

        results = self.collection.query(
            query_embeddings=[query_embedding.vector],
            n_results=options.limit,
            where=where if where else None,
            include=[
                "metadatas",
                "distances",
            ],
        )

        search_results: list[SearchResult] = []

        ids = results.get("ids", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for index, chunk_id in enumerate(ids):

            metadata = metadatas[index] or {}

            distance = float(distances[index])

            similarity = 1 - distance

            if (
                options.score_threshold is not None
                and similarity < options.score_threshold
            ):
                continue

            embedding = Embedding(
                chunk_id=UUID(chunk_id),
                tenant_id=UUID(metadata["tenant_id"]),
                model_profile_id=UUID(
                    metadata["model_profile_id"]
                ),
                vector=[],
            )

            search_results.append(
                SearchResult(
                    embedding=embedding,
                    score=similarity,
                )
            )

        return search_results

    async def mmr_search(
        self,
        query_embedding: Embedding,
        *,
        filters: SearchFilter,
        options: SearchOptions | None = None,
    ) -> list[SearchResult]:

        raise NotImplementedError(
            "MMR search is not implemented."
        )

    async def count(
        self,
        tenant_id: UUID,
    ) -> int:

        results = self.collection.get(
            where={
                "tenant_id": str(tenant_id),
            },
            include=[],
        )

        return len(results["ids"])

    async def exists(
        self,
        tenant_id: UUID,
        chunk_id: UUID,
    ) -> bool:

        results = self.collection.get(
            ids=[str(chunk_id)],
            where={
                "tenant_id": str(tenant_id),
            },
            include=[],
        )

        return len(results["ids"]) > 0