"""
GraphRAGRetriever (packages/knowledge/retrievers/providers/graph_rag.py)
— pure logic tests against a fake inner retriever, fake vector store,
and fake entity/relationship repositories. No real DB/Chroma, mirroring
tests/unit/test_multi_vector_retriever.py's fake-collaborator structure.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from packages.domain.models.document_chunk import DocumentChunk
from packages.domain.models.entity import Entity
from packages.domain.models.relationship import Relationship
from packages.knowledge.retrievers.providers.graph_rag import GraphRAGRetriever
from packages.knowledge.retrievers.schemas import RetrievalRequest
from packages.knowledge.vectorstores.schema import SearchFilter, SearchResult


def _chunk(document_id, chunk_index: int, content: str) -> DocumentChunk:
    return DocumentChunk(
        id=uuid4(),
        tenant_id=uuid4(),
        document_id=document_id,
        chunk_index=chunk_index,
        content=content,
        token_count=1,
        character_count=len(content),
        metadata_={},
    )


def _entity(name: str, entity_type: str | None = None) -> Entity:
    return Entity(
        id=uuid4(),
        tenant_id=uuid4(),
        name=name,
        name_lower=name.lower(),
        entity_type=entity_type,
    )


def _relationship(source: Entity, target: Entity) -> Relationship:
    return Relationship(
        id=uuid4(),
        tenant_id=uuid4(),
        source_entity_id=source.id,
        target_entity_id=target.id,
        relationship_type="related_to",
        document_id=uuid4(),
    )


class _FakeInnerRetriever:
    def __init__(self, matches: list[SearchResult]) -> None:
        self._matches = matches

    async def retrieve(self, _request: RetrievalRequest) -> list[SearchResult]:
        return self._matches


class _FakeVectorStore:
    def __init__(self, results_by_document: dict[object, list[SearchResult]]) -> None:
        self._results = results_by_document
        self.received_document_ids: list[object] = []

    async def similarity_search(self, *, query_embedding, filters: SearchFilter, options=None):
        self.received_document_ids.append(filters.document_id)
        return self._results.get(filters.document_id, [])


class _FakeEntityRepository:
    def __init__(self, entities: list[Entity], mentioned_document_ids: dict[object, object]) -> None:
        self._entities = entities
        self._mentioned = mentioned_document_ids

    async def list_by_tenant(self, _tenant_id):
        return self._entities

    async def list_mentioned_document_ids(self, entity_ids):
        return [
            document_id
            for entity_id, document_id in self._mentioned.items()
            if entity_id in entity_ids
        ]


class _FakeRelationshipRepository:
    def __init__(self, relationships: list[Relationship]) -> None:
        self._relationships = relationships

    async def list_neighbors(self, entity_ids):
        return [
            relationship
            for relationship in self._relationships
            if relationship.source_entity_id in entity_ids or relationship.target_entity_id in entity_ids
        ]


def _request(query: str = "a real query", document_id=None) -> RetrievalRequest:
    return RetrievalRequest(
        query_embedding=[0.1],
        filters=SearchFilter(tenant_id=uuid4(), model_profile_id=uuid4(), document_id=document_id),
        query=query,
    )


@pytest.mark.asyncio
async def test_no_entity_match_returns_only_the_inner_retrievers_results():
    document_id = uuid4()
    match = _chunk(document_id, 0, "an ordinary chunk")

    inner = _FakeInnerRetriever([SearchResult(chunk=match, score=0.5)])
    store = _FakeVectorStore({})
    entities = _FakeEntityRepository([_entity("Unrelated Co")], {})
    relationships = _FakeRelationshipRepository([])

    retriever = GraphRAGRetriever(inner, store, entities, relationships)
    results = await retriever.retrieve(_request(query="tell me about something else"))

    assert len(results) == 1
    assert results[0].chunk is match
    assert store.received_document_ids == []


@pytest.mark.asyncio
async def test_matched_entity_with_a_neighbor_pulls_in_an_extra_document():
    seed_document_id = uuid4()
    neighbor_document_id = uuid4()
    seed_chunk = _chunk(seed_document_id, 0, "chunk about Acme Corp")
    neighbor_chunk = _chunk(neighbor_document_id, 0, "chunk about Widget Inc, Acme's subsidiary")

    acme = _entity("Acme Corp")
    widget = _entity("Widget Inc")
    edge = _relationship(acme, widget)

    inner = _FakeInnerRetriever([SearchResult(chunk=seed_chunk, score=0.5)])
    store = _FakeVectorStore({neighbor_document_id: [SearchResult(chunk=neighbor_chunk, score=0.4)]})
    entities = _FakeEntityRepository(
        [acme, widget],
        {acme.id: seed_document_id, widget.id: neighbor_document_id},
    )
    relationships = _FakeRelationshipRepository([edge])

    retriever = GraphRAGRetriever(inner, store, entities, relationships)
    results = await retriever.retrieve(_request(query="What does Acme Corp do?"))

    result_chunks = {result.chunk.id for result in results}
    assert seed_chunk.id in result_chunks
    assert neighbor_chunk.id in result_chunks
    assert store.received_document_ids == [neighbor_document_id]


@pytest.mark.asyncio
async def test_document_already_covered_by_the_inner_retriever_is_not_refetched():
    document_id = uuid4()
    chunk = _chunk(document_id, 0, "chunk about Acme Corp")

    acme = _entity("Acme Corp")

    inner = _FakeInnerRetriever([SearchResult(chunk=chunk, score=0.5)])
    store = _FakeVectorStore({})
    entities = _FakeEntityRepository([acme], {acme.id: document_id})
    relationships = _FakeRelationshipRepository([])

    retriever = GraphRAGRetriever(inner, store, entities, relationships)
    results = await retriever.retrieve(_request(query="What does Acme Corp do?"))

    assert len(results) == 1
    assert store.received_document_ids == []


@pytest.mark.asyncio
async def test_document_id_already_scoped_skips_graph_expansion_entirely():
    document_id = uuid4()
    chunk = _chunk(document_id, 0, "chunk about Acme Corp")

    inner = _FakeInnerRetriever([SearchResult(chunk=chunk, score=0.5)])
    store = _FakeVectorStore({})
    entities = _FakeEntityRepository([_entity("Acme Corp")], {})
    relationships = _FakeRelationshipRepository([])

    retriever = GraphRAGRetriever(inner, store, entities, relationships)
    results = await retriever.retrieve(_request(query="What does Acme Corp do?", document_id=document_id))

    assert len(results) == 1
    assert store.received_document_ids == []
