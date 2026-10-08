# Memory repository
from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.models.memory import Memory
from packages.infrastructure.repositories.base import BaseRepository
from packages.memory.schemas import MemoryType


class MemoryRepository(BaseRepository[Memory]):
    """Repository for long-term Memory entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Memory, session)

    async def search_similar(
        self,
        *,
        tenant_id: UUID,
        query_vector: list[float],
        user_id: UUID | None = None,
        k: int = 5,
    ) -> list[Memory]:
        stmt = select(Memory).where(Memory.tenant_id == tenant_id)

        if user_id is not None:
            stmt = stmt.where(Memory.user_id == user_id)

        stmt = stmt.order_by(
            Memory.vector.cosine_distance(query_vector)
        ).limit(k)

        return await self.scalars(stmt)

    async def get_by_conversation_and_type(
        self,
        *,
        conversation_id: UUID,
        type: MemoryType,
    ) -> Memory | None:
        """
        "One per conversation" (e.g. a running summary) is an app-level
        invariant, not a DB constraint — `MemoryManager.summarize()`
        guards against creating duplicates going forward (see its own
        per-conversation lock), but this stays defensive rather than
        `scalar_one_or_none()`-and-crash: takes the most recently
        updated row if more than one somehow exists, instead of raising
        `MultipleResultsFound` and breaking every future call for that
        conversation until someone manually cleans up the DB.
        """

        stmt = (
            select(Memory)
            .where(
                Memory.conversation_id == conversation_id,
                Memory.type == type,
            )
            .order_by(Memory.updated_at.desc())
            .limit(1)
        )
        results = await self.scalars(stmt)
        return results[0] if results else None

    async def delete_by_conversation(
        self,
        conversation_id: UUID,
    ) -> None:
        stmt = delete(Memory).where(
            Memory.conversation_id == conversation_id
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def upsert_summary(
        self,
        *,
        tenant_id: UUID | None,
        user_id: UUID | None,
        conversation_id: UUID | None,
        content: str,
        importance: float,
        vector: list[float],
        metadata: dict,
    ) -> Memory:
        """
        `INSERT ... ON CONFLICT DO UPDATE` against `uq_memory_conversation_summary` (a partial
        unique index on `(conversation_id, type) WHERE type = 'SUMMARY'`,
        packages/infrastructure/database/upgrades.py) — a single atomic statement, so two
        concurrent calls for the same conversation can never both see "no row yet" and both
        insert one (the gap `MemoryManager.summarize()`'s own Redis lock didn't actually close:
        the lock's critical section only covered the check-then-act, released before this
        transaction's eventual commit at the caller's session boundary, not after it).

        `onupdate=func.now()` on `updated_at` (packages/infrastructure/database/mixins.py) is an
        ORM-level hook that only fires for a session-tracked UPDATE; a raw `ON CONFLICT DO UPDATE`
        bypasses the ORM entirely, so it's set explicitly here instead.
        """
        stmt = pg_insert(Memory).values(
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            type=MemoryType.SUMMARY,
            content=content,
            importance=importance,
            vector=vector,
            metadata_=metadata,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Memory.conversation_id, Memory.type],
            index_where=(Memory.type == MemoryType.SUMMARY),
            set_={
                "content": stmt.excluded.content,
                "importance": stmt.excluded.importance,
                "vector": stmt.excluded.vector,
                # `stmt.excluded` is keyed by the real database column name, not the ORM attribute
                # name - Memory.metadata_ maps to the actual column "metadata"
                # (mapped_column("metadata", ...), packages/domain/models/memory.py), since
                # "metadata" alone collides with SQLAlchemy's own declarative API. Confirmed live:
                # `.excluded.metadata_` raised AttributeError, `.excluded.metadata` is correct.
                "metadata": stmt.excluded.metadata,
                "updated_at": func.now(),
            },
        ).returning(Memory)

        # populate_existing: without it, a conflict path's RETURNING row gets matched against the
        # session's identity map by primary key and, if an earlier query in this same session
        # already loaded that row (e.g. the first upsert_summary() call's own `row`), the stale
        # in-memory object is returned as-is instead of being refreshed from this statement's
        # actual new values - the UPDATE truly happened in the database, but the Python object
        # handed back (and anything else reading that same identity-mapped row for the rest of
        # this session) would still show the old content. Confirmed live via a direct repro.
        result = await self.session.execute(stmt, execution_options={"populate_existing": True})
        row = result.scalar_one()
        await self.session.flush()
        return row
