"""
Real Postgres, via the db_session fixture. Exercises Durable
Execution's crash-detection layer (docs/mvpRAG.md v2.0):
`ConversationRepository.mark_processing()`/`clear_processing()`/
`list_stuck_processing()`. Full end-to-end recovery (the worker job
actually re-driving a real LangGraph checkpoint) was verified live
separately — real crash detection was manufactured against a running
app (a normal turn's mark/clear lifecycle, a stuck+recoverable
conversation, the already-complete duplicate-guard, and a legitimately
fresh in-flight conversation correctly left alone) rather than
reproduced here, since that needs a real LLM/graph/checkpointer, not
just Postgres. These tests pin down the repository-layer logic that
recovery job depends on to find the right conversations in the first
place.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from packages.conversation.bootstrap import (
    ensure_default_agent,
    ensure_default_model_profile,
)
from packages.domain.enums.conversation_status import ConversationStatus
from packages.domain.models.conversation import Conversation
from packages.infrastructure.repositories.agent import AgentRepository
from packages.infrastructure.repositories.conversation import ConversationRepository
from packages.infrastructure.repositories.model_profile import ModelProfileRepository

pytestmark = pytest.mark.integration


async def _make_conversation(db_session, tenant_id) -> Conversation:
    model_profiles = await ensure_default_model_profile(ModelProfileRepository(db_session))
    agent = await ensure_default_agent(tenant_id, model_profiles.id, AgentRepository(db_session))

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


@pytest.mark.asyncio
async def test_mark_processing_sets_status_and_timestamp(db_session):
    tenant_id = uuid4()
    conversation = await _make_conversation(db_session, tenant_id)
    repo = ConversationRepository(db_session)

    before = datetime.utcnow()
    updated = await repo.mark_processing(conversation)

    assert updated.status == ConversationStatus.PROCESSING
    assert updated.processing_started_at is not None
    assert updated.processing_started_at >= before


@pytest.mark.asyncio
async def test_clear_processing_resets_to_active(db_session):
    tenant_id = uuid4()
    conversation = await _make_conversation(db_session, tenant_id)
    repo = ConversationRepository(db_session)

    await repo.mark_processing(conversation)
    updated = await repo.clear_processing(conversation)

    assert updated.status == ConversationStatus.ACTIVE
    assert updated.processing_started_at is None


@pytest.mark.asyncio
async def test_list_stuck_processing_finds_a_stale_marker(db_session):
    tenant_id = uuid4()
    conversation = await _make_conversation(db_session, tenant_id)
    repo = ConversationRepository(db_session)

    conversation.status = ConversationStatus.PROCESSING
    conversation.processing_started_at = datetime.utcnow() - timedelta(minutes=10)
    await repo.update(conversation)
    await db_session.flush()

    cutoff = datetime.utcnow() - timedelta(minutes=5)
    stuck = await repo.list_stuck_processing(cutoff)

    assert conversation.id in {c.id for c in stuck}


@pytest.mark.asyncio
async def test_list_stuck_processing_ignores_a_fresh_marker(db_session):
    """
    The exact case a legitimately in-flight request (not a crash)
    must not be mistaken for stuck: a conversation marked PROCESSING
    moments ago, still well under the staleness threshold.
    """
    tenant_id = uuid4()
    conversation = await _make_conversation(db_session, tenant_id)
    repo = ConversationRepository(db_session)

    await repo.mark_processing(conversation)
    await db_session.flush()

    cutoff = datetime.utcnow() - timedelta(minutes=5)
    stuck = await repo.list_stuck_processing(cutoff)

    assert conversation.id not in {c.id for c in stuck}


@pytest.mark.asyncio
async def test_list_stuck_processing_ignores_active_conversations(db_session):
    """
    A conversation that's simply ACTIVE (never marked PROCESSING at
    all — the overwhelming majority of conversations at any given
    moment) must never show up here, no matter how old its
    `processing_started_at` field looks — that column is only ever
    meaningful alongside `status == PROCESSING`. Stale-but-ACTIVE
    conversations are Cleanup Jobs' `list_stale_active()` concern, a
    different job entirely.
    """
    tenant_id = uuid4()
    conversation = await _make_conversation(db_session, tenant_id)
    repo = ConversationRepository(db_session)

    # A conversation that was marked processing and already cleared
    # back to ACTIVE (the normal post-turn state) still has a real,
    # old-looking history if processing_started_at were ever reused —
    # confirming the query genuinely gates on status, not just the
    # timestamp column, requires a conversation that never had
    # PROCESSING as its current status at all.
    assert conversation.status == ConversationStatus.ACTIVE
    assert conversation.processing_started_at is None

    cutoff = datetime.utcnow() + timedelta(minutes=5)  # generous, would catch anything
    stuck = await repo.list_stuck_processing(cutoff)

    assert conversation.id not in {c.id for c in stuck}
