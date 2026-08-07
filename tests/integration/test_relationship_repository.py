"""
Real Postgres, via the db_session fixture (rolled back after every
test — see tests/conftest.py). Relationship (packages/domain/models/
relationship.py) — edge dedup and 1-hop neighbor traversal, the data
GraphRAGRetriever's graph expansion depends on.
"""

from uuid import uuid4

import pytest

from packages.domain.models.document import Document
from packages.domain.models.knowledge_base import KnowledgeBase
from packages.infrastructure.repositories.entity import EntityRepository
from packages.infrastructure.repositories.relationship import RelationshipRepository

pytestmark = pytest.mark.integration


async def _real_document(db_session, tenant_id) -> Document:
    """relationships.document_id has a real FK to documents — a bare
    uuid4() doesn't satisfy it, so tests that create an edge need an
    actual row."""
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
async def test_get_or_create_returns_the_same_edge_on_a_repeat_call(db_session):
    entities = EntityRepository(db_session)
    relationships = RelationshipRepository(db_session)
    tenant_id = uuid4()
    document_id = (await _real_document(db_session, tenant_id)).id

    source = await entities.get_or_create(tenant_id, f"Acme {uuid4()}", None, None)
    target = await entities.get_or_create(tenant_id, f"Widget {uuid4()}", None, None)

    first = await relationships.get_or_create(
        tenant_id, source.id, target.id, "acquired", None, document_id,
    )
    second = await relationships.get_or_create(
        tenant_id, source.id, target.id, "acquired", None, document_id,
    )

    assert first.id == second.id


@pytest.mark.asyncio
async def test_different_relationship_type_is_a_distinct_edge(db_session):
    entities = EntityRepository(db_session)
    relationships = RelationshipRepository(db_session)
    tenant_id = uuid4()
    document_id = (await _real_document(db_session, tenant_id)).id

    source = await entities.get_or_create(tenant_id, f"Acme {uuid4()}", None, None)
    target = await entities.get_or_create(tenant_id, f"Widget {uuid4()}", None, None)

    acquired = await relationships.get_or_create(
        tenant_id, source.id, target.id, "acquired", None, document_id,
    )
    competes = await relationships.get_or_create(
        tenant_id, source.id, target.id, "competes_with", None, document_id,
    )

    assert acquired.id != competes.id


@pytest.mark.asyncio
async def test_list_neighbors_finds_edges_regardless_of_direction(db_session):
    entities = EntityRepository(db_session)
    relationships = RelationshipRepository(db_session)
    tenant_id = uuid4()
    document_id = (await _real_document(db_session, tenant_id)).id

    a = await entities.get_or_create(tenant_id, f"A {uuid4()}", None, None)
    b = await entities.get_or_create(tenant_id, f"B {uuid4()}", None, None)
    c = await entities.get_or_create(tenant_id, f"C {uuid4()}", None, None)

    await relationships.get_or_create(tenant_id, a.id, b.id, "related_to", None, document_id)
    await relationships.get_or_create(tenant_id, c.id, a.id, "related_to", None, document_id)

    neighbors = await relationships.list_neighbors([a.id])

    assert len(neighbors) == 2


@pytest.mark.asyncio
async def test_list_neighbors_with_no_entities_returns_empty(db_session):
    relationships = RelationshipRepository(db_session)

    assert await relationships.list_neighbors([]) == []
