"""
Real Postgres, via the db_session fixture. Exercises the FK chain a
real chat turn produces (ModelProfile -> Agent -> Conversation ->
Message) using the same get-or-create bootstrap helpers the running
app itself uses (packages/conversation/bootstrap.py), then verifies
MessageRepository.sum_usage_by_tenant() — the tenant-scoped usage
rollup built for today's Token Usage + Cost Tracking work
(docs/mvpRAG.md v1.1) — against real, summed rows instead of trusting
the SQL by inspection.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from packages.conversation.bootstrap import (
    ensure_default_agent,
    ensure_default_model_profile,
)
from packages.domain.enums.message_role import MessageRole
from packages.domain.enums.message_status import MessageStatus
from packages.domain.models.conversation import Conversation
from packages.domain.models.message import Message
from packages.infrastructure.repositories.agent import AgentRepository
from packages.infrastructure.repositories.conversation import ConversationRepository
from packages.infrastructure.repositories.message import MessageRepository
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


async def _make_message(db_session, conversation: Conversation, *, prompt: int, completion: int, cost: str) -> Message:
    messages = MessageRepository(db_session)
    message = await messages.create(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            status=MessageStatus.COMPLETED,
            content="A test response.",
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion,
            cost=Decimal(cost),
        )
    )
    await db_session.flush()
    return message


@pytest.mark.asyncio
async def test_sum_usage_by_tenant_adds_across_multiple_messages(db_session):
    tenant_id = uuid4()
    conversation = await _make_conversation(db_session, tenant_id)

    await _make_message(db_session, conversation, prompt=100, completion=20, cost="0.001")
    await _make_message(db_session, conversation, prompt=50, completion=10, cost="0.0005")

    totals = await MessageRepository(db_session).sum_usage_by_tenant(tenant_id)

    assert totals["prompt_tokens"] == 150
    assert totals["completion_tokens"] == 30
    assert totals["total_tokens"] == 180
    assert totals["cost"] == Decimal("0.0015")


@pytest.mark.asyncio
async def test_sum_usage_by_tenant_is_isolated_per_tenant(db_session):
    tenant_a = uuid4()
    tenant_b = uuid4()

    conversation_a = await _make_conversation(db_session, tenant_a)
    conversation_b = await _make_conversation(db_session, tenant_b)

    await _make_message(db_session, conversation_a, prompt=100, completion=20, cost="0.001")
    await _make_message(db_session, conversation_b, prompt=999, completion=999, cost="9.0")

    totals_a = await MessageRepository(db_session).sum_usage_by_tenant(tenant_a)

    assert totals_a["prompt_tokens"] == 100
    assert totals_a["completion_tokens"] == 20
    assert totals_a["cost"] == Decimal("0.001")


@pytest.mark.asyncio
async def test_sum_usage_by_tenant_with_no_messages_returns_zeroed_totals(db_session):
    totals = await MessageRepository(db_session).sum_usage_by_tenant(uuid4())

    assert totals == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cost": Decimal(0),
    }
