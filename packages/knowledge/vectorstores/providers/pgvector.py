from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select, text
from sqlalchemy.dialects.postgresql import array as pg_array
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.domain.enums.document_status import DocumentStatus
from packages.domain.models.document import Document
from packages.domain.models.document_chunk import DocumentChunk
from packages.domain.models.embedding import Embedding
from packages.knowledge.vectorstores.base import BaseVectorStore
from packages.knowledge.vectorstores.schema import (
    SearchFilter,
    SearchOptions,
    SearchResult,
)


def _retrievable_chunk(filters: SearchFilter):
    """
    Only chunks of a live, fully ingested document may be returned by retrieval: not a superseded
    version, not a document still processing or failed, not a deleted one - and only documents the
    caller may see (restricted ones need clearance) that match the requested metadata filters.
    Applied inside the search query itself so excluded content never leaves the database.
    """
    conditions = [
        Document.is_current.is_(True),
        Document.status == DocumentStatus.READY,
        Document.is_deleted.is_(False),
    ]

    if not filters.include_restricted:
        # Open documents, plus restricted ones this caller was let into by role or by user id.
        grants = []
        if filters.user_roles:
            grants.append(Document.allowed_roles.has_any(pg_array(list(filters.user_roles))))
        if filters.user_id:
            grants.append(Document.allowed_users.contains([filters.user_id]))
        conditions.append(
            or_(Document.visibility.is_(None), Document.visibility == "tenant", *grants)
        )
    if filters.knowledge_base_id is not None:
        conditions.append(Document.knowledge_base_id == filters.knowledge_base_id)
    if filters.document_ids:
        conditions.append(Document.id.in_(filters.document_ids))
    if filters.document_types:
        conditions.append(Document.document_type.in_(filters.document_types))
    if filters.categories:
        conditions.append(Document.category.in_(filters.categories))
    if filters.language:
        conditions.append(Document.language == filters.language)
    if filters.tags:
        conditions.append(Document.tags.contains(filters.tags))
    if filters.source_types:
        # Documents ingested before sources existed are uploads.
        conditions.append(func.coalesce(Document.source_type, "upload").in_(filters.source_types))
    if filters.source_ids:
        conditions.append(Document.source_id.in_(filters.source_ids))

    return Embedding.chunk.has(DocumentChunk.document.has(and_(*conditions)))


async def _scope_session_to_tenant(session: AsyncSession, tenant_id: UUID) -> None:
    """
    Tells Postgres which tenant this transaction serves (`app.tenant_id`, transaction-local).
    Row-level-security policies on the tenant tables then enforce it in the database even if a
    query were ever written without its tenant filter (see infrastructure/database/upgrades.py).
    """
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tenant, true)"),
        {"tenant": str(tenant_id)},
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
        query_embedding: list[float],
        *,
        filters: SearchFilter,
        options: SearchOptions | None = None,
    ) -> list[SearchResult]:
        """
        Semantic similarity search using pgvector cosine distance.
        """

        options = options or SearchOptions()

        await _scope_session_to_tenant(self.session, filters.tenant_id)

        stmt = (
            select(
                Embedding,
                Embedding.vector.cosine_distance(
                    query_embedding,
                ).label("distance"),
            )
            .options(
                selectinload(Embedding.chunk),
                selectinload(Embedding.model_profile),
            )
            .where(
                Embedding.tenant_id == filters.tenant_id,
                Embedding.model_profile_id == filters.model_profile_id,
                _retrievable_chunk(filters),
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
                    chunk=embedding.chunk,
                    score=similarity,
                )
            )

        return results

    async def mmr_search(
        self,
        query_embedding: list[float],
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

    async def list_chunks(
        self,
        *,
        filters: SearchFilter,
        limit: int = 500,
    ) -> list[SearchResult]:
        """
        Bounded, unranked candidate pool for keyword (BM25) scoring.
        """

        await _scope_session_to_tenant(self.session, filters.tenant_id)

        stmt = (
            select(Embedding)
            .options(
                selectinload(Embedding.chunk),
                selectinload(Embedding.model_profile),
            )
            .where(
                Embedding.tenant_id == filters.tenant_id,
                Embedding.model_profile_id == filters.model_profile_id,
                _retrievable_chunk(filters),
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

        stmt = stmt.limit(limit)

        rows = (await self.session.execute(stmt)).scalars().all()

        return [
            SearchResult(chunk=embedding.chunk, score=0.0)
            for embedding in rows
        ]

    async def add(
        self,
        embedding: Embedding,
        *,
        representation_type: str | None = None,
    ) -> None:
        """
        `representation_type` mirrors ChromaVectorStore.add()'s own
        parameter (Multi Vector Retriever, docs/mvpRAG.md v2.0) — but
        unlike Chroma, which has to duplicate it into a separate flat
        metadata dict, here it's just written onto the real
        `DocumentChunk.metadata_` column the chunk is about to be
        persisted with. MultiVectorRetriever reads it back via
        `chunk.metadata_.get("representation_type")` either way, so
        both backends satisfy the same contract from the retriever's
        point of view.
        """

        if representation_type is not None and embedding.chunk is not None:
            embedding.chunk.metadata_ = {
                **embedding.chunk.metadata_,
                "representation_type": representation_type,
            }

        self.session.add(embedding)
        await self.session.flush()

    async def add_many(
        self,
        embeddings: list[Embedding],
    ) -> None:

        self.session.add_all(embeddings)
        await self.session.flush()

    async def delete_chunk(
        self,
        tenant_id: UUID,
        chunk_id: UUID,
    ) -> int:

        stmt = delete(Embedding).where(
            Embedding.tenant_id == tenant_id,
            Embedding.chunk_id == chunk_id,
        )

        result = await self.session.execute(stmt)

        return result.rowcount or 0

    async def delete_document(
        self,
        tenant_id: UUID,
        document_id: UUID,
    ) -> int:

        stmt = delete(Embedding).where(
            Embedding.tenant_id == tenant_id,
            Embedding.chunk.has(document_id=document_id),
        )

        result = await self.session.execute(stmt)

        # The chunk rows go too. Leaving them behind (as this once did) orphaned them, and made a
        # re-index collide with its own old chunks on (document_id, chunk_index).
        await self.session.execute(
            delete(DocumentChunk)
            .where(
                DocumentChunk.tenant_id == tenant_id,
                DocumentChunk.document_id == document_id,
            )
            # Drops the deleted rows from the session's identity map without expiring unrelated
            # objects (an expire here made the re-index's own Document lazy-load and fail).
            .execution_options(synchronize_session="fetch")
        )

        return result.rowcount or 0

    async def clear(
        self,
        tenant_id: UUID,
    ) -> int:

        stmt = delete(Embedding).where(
            Embedding.tenant_id == tenant_id,
        )

        result = await self.session.execute(stmt)

        return result.rowcount or 0

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