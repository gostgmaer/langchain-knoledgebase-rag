"""
PostgresMemoryStore and PgVectorMemoryRetriever (packages/memory/implementations/) — zero direct
test coverage before this. Both switched from an already-bound MemoryRepository to a raw
session_factory (docs/BUGS.md item 69), opening their own session per call — this is what makes
them safe to wire as process-wide Singletons. Real Postgres via the `session_factory` fixture
(tests/conftest.py); a fake embeddings client (no real embedding API call needed to prove the
session-per-call wiring is correct).
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from packages.conversation.bootstrap import ensure_default_agent, ensure_default_model_profile
from packages.domain.models.conversation import Conversation
from packages.infrastructure.repositories.agent import AgentRepository
from packages.infrastructure.repositories.conversation import ConversationRepository
from packages.infrastructure.repositories.model_profile import ModelProfileRepository
from packages.memory.implementations.pgvector_retriever import PgVectorMemoryRetriever
from packages.memory.implementations.postgres_store import PostgresMemoryStore
from packages.memory.schemas import (
    CreateMemoryRequest,
    MemoryType,
    SearchMemoryRequest,
    UpdateMemoryRequest,
)

pytestmark = pytest.mark.integration

_VECTOR = [0.0] * 1536


class _FakeEmbeddingsClient:
    async def aembed_query(self, _text: str) -> list[float]:
        return _VECTOR


def _embeddings() -> SimpleNamespace:
    return SimpleNamespace(client=_FakeEmbeddingsClient())


async def _conversation(db_session, tenant_id) -> Conversation:
    model_profile = await ensure_default_model_profile(ModelProfileRepository(db_session))
    agent = await ensure_default_agent(tenant_id, model_profile.id, AgentRepository(db_session))
    conversation = await ConversationRepository(db_session).create(
        Conversation(
            tenant_id=tenant_id, agent_id=agent.id, user_id=uuid4(),
            session_id=f"test-{uuid4()}", title="Test conversation",
        )
    )
    await db_session.flush()
    return conversation


@pytest.mark.asyncio
async def test_create_persists_a_real_row_and_returns_a_fact(session_factory):
    store = PostgresMemoryStore(session_factory, _embeddings())
    tenant_id, user_id = uuid4(), uuid4()

    fact = await store.create(
        CreateMemoryRequest(type=MemoryType.FACT, content="Likes Rust.", tenant_id=tenant_id, user_id=user_id)
    )

    assert fact.content == "Likes Rust."
    fetched = await store.get(fact.id)
    assert fetched is not None
    assert fetched.content == "Likes Rust."
    assert fetched.tenant_id == tenant_id


@pytest.mark.asyncio
async def test_create_many_creates_every_fact_as_its_own_committed_row(session_factory):
    """
    The session-per-call shape (docs/BUGS.md item 69) means create_many() is no longer one
    all-or-nothing transaction - each fact now commits independently as soon as its own create()
    call returns, a deliberate trade-off (a mid-batch failure keeps whichever facts succeeded
    before it instead of losing the whole batch). Verified here by reading each row back through
    a second, independent call to get() - proof it's really committed, not just returned in memory.
    """
    store = PostgresMemoryStore(session_factory, _embeddings())
    tenant_id, user_id = uuid4(), uuid4()

    requests = [
        CreateMemoryRequest(type=MemoryType.FACT, content="Fact one.", tenant_id=tenant_id, user_id=user_id),
        CreateMemoryRequest(type=MemoryType.FACT, content="Fact two.", tenant_id=tenant_id, user_id=user_id),
    ]
    results = await store.create_many(requests)

    assert [r.content for r in results] == ["Fact one.", "Fact two."]
    for result in results:
        assert (await store.get(result.id)) is not None


@pytest.mark.asyncio
async def test_get_returns_none_for_a_missing_memory(session_factory):
    store = PostgresMemoryStore(session_factory, _embeddings())

    assert await store.get(uuid4()) is None


@pytest.mark.asyncio
async def test_update_changes_content_importance_and_metadata(session_factory):
    store = PostgresMemoryStore(session_factory, _embeddings())
    fact = await store.create(
        CreateMemoryRequest(type=MemoryType.FACT, content="Original.", tenant_id=uuid4(), user_id=uuid4())
    )

    updated = await store.update(
        fact.id, UpdateMemoryRequest(content="Updated.", importance=0.9, metadata={"k": "v"})
    )

    assert updated.content == "Updated."
    assert updated.importance == 0.9
    assert updated.metadata == {"k": "v"}


@pytest.mark.asyncio
async def test_update_a_missing_memory_raises(session_factory):
    store = PostgresMemoryStore(session_factory, _embeddings())

    with pytest.raises(ValueError, match="not found"):
        await store.update(uuid4(), UpdateMemoryRequest(content="x"))


@pytest.mark.asyncio
async def test_delete_removes_the_row(session_factory):
    store = PostgresMemoryStore(session_factory, _embeddings())
    fact = await store.create(
        CreateMemoryRequest(type=MemoryType.FACT, content="Delete me.", tenant_id=uuid4(), user_id=uuid4())
    )

    await store.delete(fact.id)

    assert await store.get(fact.id) is None


@pytest.mark.asyncio
async def test_clear_removes_every_memory_for_a_conversation(db_session, session_factory):
    store = PostgresMemoryStore(session_factory, _embeddings())
    tenant_id = uuid4()
    conversation = await _conversation(db_session, tenant_id)
    await db_session.commit()

    fact = await store.create(
        CreateMemoryRequest(
            type=MemoryType.FACT, content="Scoped fact.", tenant_id=tenant_id,
            user_id=uuid4(), conversation_id=conversation.id,
        )
    )

    await store.clear(conversation.id)

    assert await store.get(fact.id) is None


@pytest.mark.asyncio
async def test_upsert_summary_replaces_not_duplicates(session_factory, db_session):
    store = PostgresMemoryStore(session_factory, _embeddings())
    tenant_id = uuid4()
    conversation = await _conversation(db_session, tenant_id)
    await db_session.commit()

    first = await store.upsert_summary(
        CreateMemoryRequest(
            type=MemoryType.SUMMARY, content="Turn one.", tenant_id=tenant_id,
            user_id=uuid4(), conversation_id=conversation.id,
        )
    )
    second = await store.upsert_summary(
        CreateMemoryRequest(
            type=MemoryType.SUMMARY, content="Turn two.", tenant_id=tenant_id,
            user_id=uuid4(), conversation_id=conversation.id,
        )
    )

    assert second.id == first.id
    assert second.content == "Turn two."


@pytest.mark.asyncio
async def test_store_search_finds_a_created_memory(session_factory):
    store = PostgresMemoryStore(session_factory, _embeddings())
    tenant_id, user_id = uuid4(), uuid4()
    fact = await store.create(
        CreateMemoryRequest(type=MemoryType.FACT, content="Findable fact.", tenant_id=tenant_id, user_id=user_id)
    )

    response = await store.search(SearchMemoryRequest(query="anything", tenant_id=tenant_id, user_id=user_id))

    assert fact.id in {result.memory.id for result in response.results}


@pytest.mark.asyncio
async def test_retriever_search_finds_a_created_memory(session_factory):
    store = PostgresMemoryStore(session_factory, _embeddings())
    retriever = PgVectorMemoryRetriever(session_factory, _embeddings())
    tenant_id, user_id = uuid4(), uuid4()
    fact = await store.create(
        CreateMemoryRequest(type=MemoryType.FACT, content="Retriever fact.", tenant_id=tenant_id, user_id=user_id)
    )

    response = await retriever.search(SearchMemoryRequest(query="anything", tenant_id=tenant_id, user_id=user_id))

    assert fact.id in {result.memory.id for result in response.results}
