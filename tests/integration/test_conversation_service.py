"""
ConversationService (packages/application/services/conversation_service.py) — zero direct test
coverage before this (docs/BUGS.md items 20/F3) despite being the service every single chat turn
goes through first (ChatService._get_conversation calls get_or_create on every request). Real
Postgres via the db_session fixture, same pattern as test_conversation_durable_execution.py.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from packages.application.dto.conversation import CreateConversationRequest
from packages.application.exceptions import ResourceNotFoundError
from packages.application.services.conversation_service import ConversationService
from packages.conversation.bootstrap import ensure_default_agent, ensure_default_model_profile
from packages.domain.enums.conversation_status import ConversationStatus
from packages.infrastructure.repositories.agent import AgentRepository
from packages.infrastructure.repositories.model_profile import ModelProfileRepository
from packages.infrastructure.repositories.unit_of_work import UnitOfWork

pytestmark = pytest.mark.integration


async def _request(db_session, tenant_id, *, session_id: str | None = None) -> CreateConversationRequest:
    model_profile = await ensure_default_model_profile(ModelProfileRepository(db_session))
    agent = await ensure_default_agent(tenant_id, model_profile.id, AgentRepository(db_session))
    return CreateConversationRequest(
        tenant_id=tenant_id,
        user_id=uuid4(),
        agent_id=agent.id,
        session_id=session_id or f"test-{uuid4()}",
        title="Test conversation",
    )


@pytest.mark.asyncio
async def test_get_raises_not_found_for_a_missing_conversation(db_session):
    service = ConversationService(UnitOfWork(db_session))

    with pytest.raises(ResourceNotFoundError):
        await service.get(uuid4())


@pytest.mark.asyncio
async def test_create_persists_and_returns_a_conversation_response(db_session):
    tenant_id = uuid4()
    service = ConversationService(UnitOfWork(db_session))
    request = await _request(db_session, tenant_id)

    created = await service.create(request)

    assert created.tenant_id == tenant_id
    assert created.session_id == request.session_id
    assert created.status == ConversationStatus.ACTIVE
    assert created.total_messages == 0

    fetched = await service.get(created.id)
    assert fetched.id == created.id
    assert fetched.session_id == request.session_id


@pytest.mark.asyncio
async def test_get_by_session_returns_none_when_no_conversation_exists_for_that_session(db_session):
    service = ConversationService(UnitOfWork(db_session))

    assert await service.get_by_session(f"never-created-{uuid4()}") is None


@pytest.mark.asyncio
async def test_get_or_create_reuses_the_existing_conversation_for_the_same_session(db_session):
    """
    The exact behavior every chat turn depends on: a second message in the same session must
    land on the same conversation row, never silently create a second one.
    """
    tenant_id = uuid4()
    service = ConversationService(UnitOfWork(db_session))
    request = await _request(db_session, tenant_id, session_id=f"shared-{uuid4()}")

    first = await service.get_or_create(request)
    second = await service.get_or_create(request)

    assert first.id == second.id


@pytest.mark.asyncio
async def test_get_or_create_creates_a_new_conversation_for_a_new_session(db_session):
    tenant_id = uuid4()
    service = ConversationService(UnitOfWork(db_session))
    request = await _request(db_session, tenant_id)

    created = await service.get_or_create(request)

    assert created.session_id == request.session_id
    refetched = await service.get(created.id)
    assert refetched.id == created.id


@pytest.mark.asyncio
async def test_close_marks_the_conversation_completed_and_sets_ended_at(db_session):
    tenant_id = uuid4()
    service = ConversationService(UnitOfWork(db_session))
    request = await _request(db_session, tenant_id)
    created = await service.create(request)
    assert created.ended_at is None

    closed = await service.close(created.id)

    assert closed.status == ConversationStatus.COMPLETED
    assert closed.ended_at is not None


@pytest.mark.asyncio
async def test_close_raises_not_found_for_a_missing_conversation(db_session):
    service = ConversationService(UnitOfWork(db_session))

    with pytest.raises(ResourceNotFoundError):
        await service.close(uuid4())


@pytest.mark.asyncio
async def test_touch_increments_total_messages_by_two_and_sets_last_message_at(db_session):
    """
    += 2, not += 1: one chat turn writes one user message and one assistant message, and this is
    the one place that count gets bumped (docs/BUGS.md F3) - easy to silently regress to +=1 (an
    off-by-one that would make every conversation's displayed message count half of reality)
    without a test pinning down the actual contract.
    """
    tenant_id = uuid4()
    service = ConversationService(UnitOfWork(db_session))
    request = await _request(db_session, tenant_id)
    created = await service.create(request)
    assert created.total_messages == 0
    assert created.last_message_at is None

    await service.touch(created.id)

    touched = await service.get(created.id)
    assert touched.total_messages == 2
    assert touched.last_message_at is not None

    await service.touch(created.id)
    touched_again = await service.get(created.id)
    assert touched_again.total_messages == 4


@pytest.mark.asyncio
async def test_touch_raises_not_found_for_a_missing_conversation(db_session):
    service = ConversationService(UnitOfWork(db_session))

    with pytest.raises(ResourceNotFoundError):
        await service.touch(uuid4())
