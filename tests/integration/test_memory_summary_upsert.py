"""
Real Postgres, via the db_session fixture. Exercises
MemoryRepository.upsert_summary() -- the atomic ON CONFLICT DO UPDATE added to close a real gap:
MemoryManager.summarize()'s old check-then-act (get_by_conversation_and_type() then create()/
update()) could still leave two SUMMARY rows for the same conversation, because its Redis lock's
critical section was released before the transaction holding the create was actually committed at
the caller's own session boundary. These tests verify the new upsert's create-then-replace
semantics against the real uq_memory_conversation_summary partial unique index, not just by
inspecting the SQL.
"""

from uuid import uuid4

import pytest
from sqlalchemy import select

from packages.conversation.bootstrap import (
    ensure_default_agent,
    ensure_default_model_profile,
)
from packages.domain.models.conversation import Conversation
from packages.domain.models.memory import Memory
from packages.infrastructure.repositories.agent import AgentRepository
from packages.infrastructure.repositories.conversation import ConversationRepository
from packages.infrastructure.repositories.memory import MemoryRepository
from packages.infrastructure.repositories.model_profile import ModelProfileRepository
from packages.memory.schemas import MemoryType

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_VECTOR = [0.0] * 1536


async def _make_conversation(db_session, tenant_id) -> Conversation:
    """
    memories.conversation_id is a real foreign key to conversations.id -- upsert_summary() needs
    a real row to point at, same as every other integration test touching Message/Conversation
    (tests/integration/test_message_usage_repository.py's own _make_conversation).
    """
    model_profile = await ensure_default_model_profile(ModelProfileRepository(db_session))
    agent = await ensure_default_agent(tenant_id, model_profile.id, AgentRepository(db_session))

    conversations = ConversationRepository(db_session)
    conversation = await conversations.create(
        Conversation(
            tenant_id=tenant_id,
            agent_id=agent.id,
            user_id=uuid4(),
            session_id=f"test-{uuid4()}",
            title="Test conversation",
        )
    )
    await db_session.flush()
    return conversation


async def _rows_for(db_session, conversation_id) -> list[Memory]:
    result = await db_session.execute(
        select(Memory).where(
            Memory.conversation_id == conversation_id,
            Memory.type == MemoryType.SUMMARY,
        )
    )
    return list(result.scalars().all())


async def test_the_first_upsert_creates_a_summary_row(db_session):
    tenant_id = uuid4()
    conversation = await _make_conversation(db_session, tenant_id)
    repo = MemoryRepository(db_session)

    row = await repo.upsert_summary(
        tenant_id=tenant_id,
        user_id=uuid4(),
        conversation_id=conversation.id,
        content="First summary.",
        importance=0.5,
        vector=_VECTOR,
        metadata={},
    )

    assert row.content == "First summary."
    rows = await _rows_for(db_session, conversation.id)
    assert len(rows) == 1
    assert rows[0].id == row.id


async def test_a_second_upsert_for_the_same_conversation_replaces_not_duplicates(db_session):
    """
    This is the exact scenario the old check-then-act race could get wrong: two "concurrent"
    summarize() calls for the same conversation. Sequential calls against the real unique index
    can't reproduce the original timing race itself, but they do prove the fix's actual mechanism
    (ON CONFLICT DO UPDATE against uq_memory_conversation_summary) behaves correctly -- exactly one
    row survives, and it has the newer content, not an orphaned duplicate.
    """
    tenant_id = uuid4()
    user_id = uuid4()
    conversation = await _make_conversation(db_session, tenant_id)
    repo = MemoryRepository(db_session)

    first = await repo.upsert_summary(
        tenant_id=tenant_id,
        user_id=user_id,
        conversation_id=conversation.id,
        content="Turn one summary.",
        importance=0.5,
        vector=_VECTOR,
        metadata={},
    )

    second = await repo.upsert_summary(
        tenant_id=tenant_id,
        user_id=user_id,
        conversation_id=conversation.id,
        content="Turn two summary.",
        importance=0.7,
        vector=_VECTOR,
        metadata={"turns": 2},
    )

    assert second.id == first.id
    rows = await _rows_for(db_session, conversation.id)
    assert len(rows) == 1
    assert rows[0].content == "Turn two summary."
    assert rows[0].importance == 0.7
    assert rows[0].metadata_ == {"turns": 2}


async def test_different_conversations_each_get_their_own_summary_row(db_session):
    repo = MemoryRepository(db_session)
    tenant_id = uuid4()
    conversation_a = await _make_conversation(db_session, tenant_id)
    conversation_b = await _make_conversation(db_session, tenant_id)

    await repo.upsert_summary(
        tenant_id=tenant_id, user_id=uuid4(), conversation_id=conversation_a.id,
        content="A's summary.", importance=0.5, vector=_VECTOR, metadata={},
    )
    await repo.upsert_summary(
        tenant_id=tenant_id, user_id=uuid4(), conversation_id=conversation_b.id,
        content="B's summary.", importance=0.5, vector=_VECTOR, metadata={},
    )

    assert len(await _rows_for(db_session, conversation_a.id)) == 1
    assert len(await _rows_for(db_session, conversation_b.id)) == 1
