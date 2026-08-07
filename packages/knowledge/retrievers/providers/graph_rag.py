# graph_rag.py
from __future__ import annotations

from dataclasses import replace

from packages.domain.models.entity import Entity
from packages.infrastructure.repositories.entity import EntityRepository
from packages.infrastructure.repositories.relationship import RelationshipRepository
from packages.knowledge.retrievers.base import BaseRetriever
from packages.knowledge.retrievers.schemas import RetrievalRequest
from packages.knowledge.vectorstores.manager import VectorStoreManager
from packages.knowledge.vectorstores.schema import SearchOptions, SearchResult

_ENTITY_MATCH_LIMIT = 5
_NEIGHBOR_CANDIDATES_PER_DOCUMENT = 3
_NEIGHBOR_RESULTS_PER_DOCUMENT = 2


def _match_entities(
    query_lower: str,
    entities: list[Entity],
    limit: int,
) -> list[Entity]:
    """
    Cheap substring matching — entity names appearing literally in the
    query text — deliberately not another LLM call, matching this
    project's established cost-consciousness (SelfQueryRetriever made
    the identical trade-off). Pure function, trivially unit-testable
    without a database.
    """

    matches = [entity for entity in entities if entity.name_lower in query_lower]
    matches.sort(key=lambda entity: len(entity.name_lower), reverse=True)

    return matches[:limit]


class GraphRAGRetriever(BaseRetriever):
    """
    Wraps an inner retriever (hybrid by default) and expands its
    results with a 1-hop knowledge-graph traversal — same composition
    pattern SelfQueryRetriever/ParentDocumentRetriever/
    MultiVectorRetriever already use, not a replacement search
    algorithm.

    Entities named in the query seed a 1-hop relationship lookup;
    documents that mention a neighboring entity (but weren't already
    surfaced by the inner retriever) contribute a few of their own
    real, top-scoring chunks — mirroring MultiVectorRetriever's
    "resolve a signal back to real chunk content" pattern. The graph
    traversal itself is never returned as literal context, only real
    chunk content is.
    """

    def __init__(
        self,
        inner: BaseRetriever,
        vector_store: VectorStoreManager,
        entity_repository: EntityRepository,
        relationship_repository: RelationshipRepository,
    ) -> None:
        self._inner = inner
        self._vector_store = vector_store
        self._entities = entity_repository
        self._relationships = relationship_repository

    async def retrieve(
        self,
        request: RetrievalRequest,
    ) -> list[SearchResult]:

        matches = await self._inner.retrieve(request)

        deduped: dict[object, SearchResult] = {}

        def _keep_best(result: SearchResult) -> None:
            existing = deduped.get(result.chunk.id)
            if existing is None or result.score > existing.score:
                deduped[result.chunk.id] = result

        for match in matches:
            _keep_best(match)

        # A caller already scoped to one document (e.g.
        # MultiVectorRetriever's own resolution pass) doesn't need a
        # tenant-wide traversal layered on top.
        if not request.query.strip() or request.filters.document_id is not None:
            return list(deduped.values())

        tenant_entities = await self._entities.list_by_tenant(request.filters.tenant_id)
        seed_entities = _match_entities(request.query.lower(), tenant_entities, _ENTITY_MATCH_LIMIT)

        if not seed_entities:
            return list(deduped.values())

        seed_ids = [entity.id for entity in seed_entities]
        neighbor_relationships = await self._relationships.list_neighbors(seed_ids)

        expanded_ids = set(seed_ids)
        for relationship in neighbor_relationships:
            expanded_ids.add(relationship.source_entity_id)
            expanded_ids.add(relationship.target_entity_id)

        document_ids = await self._entities.list_mentioned_document_ids(list(expanded_ids))
        already_covered = {result.chunk.document_id for result in deduped.values()}

        for document_id in document_ids:
            if document_id in already_covered:
                continue

            candidates = await self._vector_store.similarity_search(
                query_embedding=request.query_embedding,
                filters=replace(request.filters, document_id=document_id),
                options=SearchOptions(limit=_NEIGHBOR_CANDIDATES_PER_DOCUMENT),
            )

            for candidate in candidates[:_NEIGHBOR_RESULTS_PER_DOCUMENT]:
                _keep_best(candidate)

        return list(deduped.values())
