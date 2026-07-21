# chroma.py - Future
from __future__ import annotations

from uuid import UUID

import chromadb
from chromadb.api.models.Collection import Collection

from packages.domain.models.document_chunk import DocumentChunk
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
        query_embedding: list[float],
        *,
        filters: SearchFilter,
        options: SearchOptions | None = None,
    ) -> list[SearchResult]:

        options = options or SearchOptions()

        conditions: list[dict[str, object]] = [
            {"tenant_id": str(filters.tenant_id)},
            {"model_profile_id": str(filters.model_profile_id)},
        ]

        if filters.document_id:
            conditions.append({"document_id": str(filters.document_id)})

        if filters.metadata:
            conditions.extend(
                {key: value} for key, value in filters.metadata.items()
            )

        where = {"$and": conditions} if len(conditions) > 1 else conditions[0]

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=options.limit,
            where=where,
            include=[
                "metadatas",
                "distances",
                "documents",
            ],
        )

        search_results: list[SearchResult] = []

        ids = results.get("ids", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        contents = results.get("documents", [[]])[0]

        for index, chunk_id in enumerate(ids):

            metadata = metadatas[index] or {}

            distance = float(distances[index])

            similarity = 1 - distance

            if (
                options.score_threshold is not None
                and similarity < options.score_threshold
            ):
                continue

            content = contents[index] if index < len(contents) else ""

            chunk = DocumentChunk(
                id=UUID(chunk_id),
                tenant_id=UUID(metadata["tenant_id"]),
                document_id=UUID(metadata.get("document_id", chunk_id)),
                chunk_index=int(metadata.get("chunk_index", 0)),
                content=content,
                token_count=int(metadata.get("token_count", 0)),
                character_count=len(content),
                metadata_=metadata,
            )

            search_results.append(
                SearchResult(
                    chunk=chunk,
                    score=similarity,
                )
            )

        return search_results

    async def list_chunks(
        self,
        *,
        filters: SearchFilter,
        limit: int = 500,
    ) -> list[SearchResult]:

        conditions: list[dict[str, object]] = [
            {"tenant_id": str(filters.tenant_id)},
            {"model_profile_id": str(filters.model_profile_id)},
        ]

        if filters.document_id:
            conditions.append({"document_id": str(filters.document_id)})

        if filters.metadata:
            conditions.extend(
                {key: value} for key, value in filters.metadata.items()
            )

        where = {"$and": conditions} if len(conditions) > 1 else conditions[0]

        results = self.collection.get(
            where=where,
            limit=limit,
            include=[
                "metadatas",
                "documents",
            ],
        )

        search_results: list[SearchResult] = []

        ids = results.get("ids", [])
        metadatas = results.get("metadatas", [])
        contents = results.get("documents", [])

        for index, chunk_id in enumerate(ids):

            metadata = metadatas[index] or {}
            content = contents[index] if index < len(contents) else ""

            chunk = DocumentChunk(
                id=UUID(chunk_id),
                tenant_id=UUID(metadata["tenant_id"]),
                document_id=UUID(metadata.get("document_id", chunk_id)),
                chunk_index=int(metadata.get("chunk_index", 0)),
                content=content,
                token_count=int(metadata.get("token_count", 0)),
                character_count=len(content),
                metadata_=metadata,
            )

            search_results.append(
                SearchResult(
                    chunk=chunk,
                    score=0.0,
                )
            )

        return search_results

    async def add(
        self,
        embedding: Embedding,
    ) -> None:

        chunk = embedding.chunk

        self.collection.add(
            ids=[str(embedding.chunk_id)],
            embeddings=[embedding.vector],
            documents=[chunk.content if chunk else ""],
            metadatas=[
                {
                    "tenant_id": str(embedding.tenant_id),
                    "model_profile_id": str(embedding.model_profile_id),
                    "document_id": str(chunk.document_id) if chunk else "",
                    "chunk_index": chunk.chunk_index if chunk else 0,
                }
            ],
        )

    async def add_many(
        self,
        embeddings: list[Embedding],
    ) -> None:

        for embedding in embeddings:
            await self.add(embedding)

    async def delete_chunk(
        self,
        tenant_id: UUID,
        chunk_id: UUID,
    ) -> int:

        existing = self.collection.get(
            ids=[str(chunk_id)],
            where={"tenant_id": str(tenant_id)},
            include=[],
        )

        if not existing["ids"]:
            return 0

        self.collection.delete(ids=[str(chunk_id)])

        return len(existing["ids"])

    async def delete_document(
        self,
        tenant_id: UUID,
        document_id: UUID,
    ) -> int:

        existing = self.collection.get(
            where={
                "$and": [
                    {"tenant_id": str(tenant_id)},
                    {"document_id": str(document_id)},
                ]
            },
            include=[],
        )

        if not existing["ids"]:
            return 0

        self.collection.delete(ids=existing["ids"])

        return len(existing["ids"])

    async def clear(
        self,
        tenant_id: UUID,
    ) -> int:

        existing = self.collection.get(
            where={"tenant_id": str(tenant_id)},
            include=[],
        )

        if not existing["ids"]:
            return 0

        self.collection.delete(ids=existing["ids"])

        return len(existing["ids"])

    async def mmr_search(
        self,
        query_embedding: list[float],
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