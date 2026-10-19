"""
MessageService (packages/application/services/message_service.py) — zero direct test coverage
before this (docs/BUGS.md items 20/F3), despite being what persists every single message of
every chat turn, including the cost/token-accounting logic ChatService's billing-adjacent reads
depend on. Real Postgres via the db_session fixture, same pattern as
test_conversation_durable_execution.py/test_conversation_service.py.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from packages.application.services.message_service import MessageService
from packages.conversation.bootstrap import ensure_default_agent, ensure_default_model_profile
from packages.domain.enums.conversation_status import ConversationStatus
from packages.domain.enums.message_role import MessageRole
from packages.domain.models.conversation import Conversation
from packages.infrastructure.repositories.agent import AgentRepository
from packages.infrastructure.repositories.model_profile import ModelProfileRepository
from packages.infrastructure.repositories.unit_of_work import UnitOfWork

pytestmark = pytest.mark.integration


async def _conversation_id(db_session) -> object:
    tenant_id = uuid4()
    model_profile = await ensure_default_model_profile(ModelProfileRepository(db_session))
    agent = await ensure_default_agent(tenant_id, model_profile.id, AgentRepository(db_session))
    uow = UnitOfWork(db_session)
    conversation = await uow.conversations.create(
        Conversation(
            tenant_id=tenant_id,
            user_id=uuid4(),
            agent_id=agent.id,
            session_id=f"test-{uuid4()}",
            title="Test conversation",
            status=ConversationStatus.ACTIVE,
        )
    )
    await db_session.flush()
    return conversation.id


@pytest.mark.asyncio
async def test_create_user_message_persists_with_the_user_role_and_content(db_session):
    conversation_id = await _conversation_id(db_session)
    service = MessageService(UnitOfWork(db_session))

    message = await service.create_user_message(conversation_id, "What's in my knowledge base?")

    assert message.conversation_id == conversation_id
    assert message.role == MessageRole.USER
    assert message.content == "What's in my knowledge base?"


@pytest.mark.asyncio
async def test_create_tool_message_persists_with_the_tool_role(db_session):
    conversation_id = await _conversation_id(db_session)
    service = MessageService(UnitOfWork(db_session))

    message = await service.create_tool_message(conversation_id, "5 results found.")

    assert message.role == MessageRole.TOOL
    assert message.content == "5 results found."


@pytest.mark.asyncio
async def test_create_system_message_persists_with_the_system_role(db_session):
    conversation_id = await _conversation_id(db_session)
    service = MessageService(UnitOfWork(db_session))

    message = await service.create_system_message(conversation_id, "You are a helpful assistant.")

    assert message.role == MessageRole.SYSTEM


@pytest.mark.asyncio
async def test_create_assistant_message_with_no_usage_skips_cost_and_token_fields(db_session):
    conversation_id = await _conversation_id(db_session)
    service = MessageService(UnitOfWork(db_session))

    message = await service.create_assistant_message(conversation_id, "The answer is 4.")

    assert message.role == MessageRole.ASSISTANT
    assert message.prompt_tokens == 0
    assert message.completion_tokens == 0
    assert message.total_tokens == 0
    assert message.cost == Decimal("0")


@pytest.mark.asyncio
async def test_create_assistant_message_computes_cost_from_usage_and_known_pricing(db_session):
    """
    Pins down the actual arithmetic (packages/config/pricing.py), not just "a cost got set" - this
    is the exact number a tenant's usage/billing view would show, so a silent regression here
    (wrong token field read, wrong price lookup) would misreport real cost without ever crashing.
    """
    conversation_id = await _conversation_id(db_session)
    service = MessageService(UnitOfWork(db_session))
    usage = {"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500}

    message = await service.create_assistant_message(
        conversation_id,
        "Here is the comparison.",
        provider="google",
        model="gemini-3.1-flash-lite",
        usage=usage,
    )

    assert message.prompt_tokens == 1000
    assert message.completion_tokens == 500
    assert message.total_tokens == 1500
    assert message.usage_metadata == usage
    # (1000 * $0.10 + 500 * $0.40) / 1_000_000 = $0.0003
    assert message.cost == Decimal("0.000300")


@pytest.mark.asyncio
async def test_create_assistant_message_skips_cost_when_usage_has_no_provider_or_model(db_session):
    """
    compute_cost() needs both a provider and a model to look up a price - usage alone (e.g. a
    turn where the model profile lookup failed) must not be treated as "$0 because unknown
    model," it must skip cost computation entirely rather than guess.
    """
    conversation_id = await _conversation_id(db_session)
    service = MessageService(UnitOfWork(db_session))

    message = await service.create_assistant_message(
        conversation_id,
        "Here is the answer.",
        usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
    )

    assert message.prompt_tokens == 100
    assert message.completion_tokens == 50
    assert message.cost == Decimal("0")


@pytest.mark.asyncio
async def test_create_assistant_message_stores_tool_calls_and_tool_results_when_present(db_session):
    conversation_id = await _conversation_id(db_session)
    service = MessageService(UnitOfWork(db_session))
    calls = [{"id": "call_1", "name": "search_knowledge_base", "args": {"query": "leave policy"}}]
    results = [{"tool_call_id": "call_1", "content": "5 results found."}]

    message = await service.create_assistant_message(
        conversation_id,
        "Found it.",
        tool_calls=calls,
        tool_results=results,
    )

    assert message.tool_calls == {"calls": calls}
    assert message.tool_results == {"results": results}


@pytest.mark.asyncio
async def test_create_assistant_message_persists_a_raw_ai_response_when_metadata_is_present(db_session):
    conversation_id = await _conversation_id(db_session)
    uow = UnitOfWork(db_session)
    service = MessageService(uow)
    raw_response = {"response_metadata": {"finish_reason": "stop"}, "additional_kwargs": {}}

    message = await service.create_assistant_message(
        conversation_id,
        "Done.",
        provider="google",
        model="gemini-3.1-flash-lite",
        raw_response=raw_response,
    )

    await db_session.flush()
    stored = await uow.ai_responses.get_by_message(message.id)
    assert stored is not None
    assert stored.provider == "google"
    assert stored.model == "gemini-3.1-flash-lite"
    assert stored.raw_response == raw_response


@pytest.mark.asyncio
async def test_create_assistant_message_skips_the_ai_response_row_when_there_is_no_real_metadata(db_session):
    """
    docs/BUGS.md's own existing note on this code: a provider response with nothing in
    response_metadata/additional_kwargs must not leave behind an empty AIResponse row.
    """
    conversation_id = await _conversation_id(db_session)
    uow = UnitOfWork(db_session)
    service = MessageService(uow)

    message = await service.create_assistant_message(
        conversation_id,
        "Done.",
        provider="google",
        model="gemini-3.1-flash-lite",
        raw_response={"response_metadata": {}, "additional_kwargs": {}},
    )

    await db_session.flush()
    stored = await uow.ai_responses.get_by_message(message.id)
    assert stored is None
