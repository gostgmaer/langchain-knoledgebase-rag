from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.domain.models.embedding import Embedding
from packages.knowledge.vectorstores.base import BaseVectorStore
from packages.knowledge.vectorstores.schema import (
    SearchFilter,
    SearchOptions,
    SearchResult,
)


class PostgresVectorStore(BaseVectorStore):
    """
    PostgreSQL pgvector implementation.
    """

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session

    async def similarity_search(
        self,
        query_embedding: Embedding,
        *,
        filters: SearchFilter,
        options: SearchOptions | None = None,
    ) -> list[SearchResult]:
        """
        Semantic similarity search using pgvector cosine distance.
        """

        options = options or SearchOptions()

        stmt = (
            select(
                Embedding,
                Embedding.vector.cosine_distance(
                    query_embedding.vector,
                ).label("distance"),
            )
            .options(
                selectinload(Embedding.chunk),
                selectinload(Embedding.model_profile),
            )
            .where(
                Embedding.tenant_id == filters.tenant_id,
                Embedding.model_profile_id == filters.model_profile_id,
            )
        )

        if filters.document_id:
            stmt = stmt.where(
                Embedding.chunk.has(
                    document_id=filters.document_id,
                )
            )

        if filters.chunk_ids:
            stmt = stmt.where(
                Embedding.chunk_id.in_(filters.chunk_ids),
            )

        stmt = (
            stmt.order_by("distance")
            .limit(options.limit)
        )

        rows = (await self.session.execute(stmt)).all()

        results: list[SearchResult] = []

        for embedding, distance in rows:
            similarity = 1 - float(distance)

            if (
                options.score_threshold is not None
                and similarity < options.score_threshold
            ):
                continue

            results.append(
                SearchResult(
                    embedding=embedding,
                    score=similarity,
                )
            )

        return results

    async def mmr_search(
        self,
        query_embedding: Embedding,
        *,
        filters: SearchFilter,
        options: SearchOptions | None = None,
    ) -> list[SearchResult]:
        """
        Placeholder implementation.
        """

        raise NotImplementedError(
            "MMR search has not been implemented."
        )

    async def count(
        self,
        tenant_id: UUID,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Embedding)
            .where(
                Embedding.tenant_id == tenant_id,
            )
        )

        return int(
            await self.session.scalar(stmt) or 0
        )

    async def exists(
        self,
        tenant_id: UUID,
        chunk_id: UUID,
    ) -> bool:
        stmt = (
            select(Embedding.id)
            .where(
                Embedding.tenant_id == tenant_id,
                Embedding.chunk_id == chunk_id,
            )
            .limit(1)
        )

        return (
            await self.session.scalar(stmt)
        ) is not None