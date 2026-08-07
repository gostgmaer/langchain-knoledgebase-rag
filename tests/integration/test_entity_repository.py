"""
Real Postgres, via the db_session fixture (rolled back after every
test — see tests/conftest.py). Entity/EntityMention (packages/domain/
models/entity.py, entity_mention.py) — dedup and mention-tracking, the
data GraphRAGRetriever's query-time entity matching and document
resolution depend on.
"""

from uuid import uuid4

import pytest

from packages.domain.models.document import Document
from packages.domain.models.knowledge_base import KnowledgeBase
from packages.infrastructure.repositories.entity import EntityRepository

pytestmark = pytest.mark.integration


async def _real_document(db_session, tenant_id) -> Document:
    """entity_mentions.document_id has a real FK to documents — a
    bare uuid4() doesn't satisfy it, so tests that record a mention
    need an actual row."""
    kb = KnowledgeBase(
        tenant_id=tenant_id,
        name="test kb",
        slug=f"test-kb-{uuid4()}",
        embedding_provider="google",
        embedding_model="text-embedding-004",
        embedding_dimension=768,
    )
    db_session.add(kb)
    await db_session.flush()

    document = Document(
        knowledge_base_id=kb.id,
        tenant_id=tenant_id,
        title="test document",
        file_id=str(uuid4()),
        file_name="test.txt",
        mime_type="text/plain",
        extension=".txt",
        size_bytes=10,
        checksum=str(uuid4()),
    )
    db_session.add(document)
    await db_session.flush()

    return document


@pytest.mark.asyncio
async def test_get_or_create_returns_the_same_row_on_a_repeat_call(db_session):
    repo = EntityRepository(db_session)
    tenant_id = uuid4()
    name = f"Acme Corp {uuid4()}"

    first = await repo.get_or_create(tenant_id, name, "organization", "a company")
    second = await repo.get_or_create(tenant_id, name, "organization", "a company")

    assert first.id == second.id


@pytest.mark.asyncio
async def test_get_or_create_is_case_insensitive_on_name(db_session):
    repo = EntityRepository(db_session)
    tenant_id = uuid4()
    base_name = f"Widget Inc {uuid4()}"

    first = await repo.get_or_create(tenant_id, base_name, "organization", None)
    second = await repo.get_or_create(tenant_id, base_name.upper(), "organization", None)

    assert first.id == second.id


@pytest.mark.asyncio
async def test_different_entity_type_is_a_distinct_entity(db_session):
    repo = EntityRepository(db_session)
    tenant_id = uuid4()
    name = f"Jordan {uuid4()}"

    person = await repo.get_or_create(tenant_id, name, "person", None)
    other = await repo.get_or_create(tenant_id, name, "product", None)

    assert person.id != other.id


@pytest.mark.asyncio
async def test_add_mention_is_idempotent_and_list_mentioned_document_ids_reflects_it(db_session):
    repo = EntityRepository(db_session)
    tenant_id = uuid4()
    document = await _real_document(db_session, tenant_id)
    document_id = document.id

    entity = await repo.get_or_create(tenant_id, f"Acme {uuid4()}", None, None)

    await repo.add_mention(entity.id, document_id, tenant_id)
    await repo.add_mention(entity.id, document_id, tenant_id)  # repeat, must not duplicate

    document_ids = await repo.list_mentioned_document_ids([entity.id])

    assert document_ids.count(document_id) == 1


@pytest.mark.asyncio
async def test_list_mentioned_document_ids_with_no_entities_returns_empty(db_session):
    repo = EntityRepository(db_session)

    assert await repo.list_mentioned_document_ids([]) == []
