"""
MultiVectorRetriever (packages/knowledge/retrievers/providers/
multi_vector.py) — pure logic tests against a fake inner retriever and
a fake vector store, no real DB/Chroma. Live-verified separately
against a real ingested document (a query phrased like the summary,
not any literal chunk, correctly resolved to the real primary chunk
content, never the synthetic summary text) — these tests pin down the
surrounding logic: resolve-and-replace, dedup, non-summary passthrough.
"""

from uuid import uuid4

import pytest

from packages.domain.models.document_chunk import DocumentChunk
from packages.knowledge.retrievers.providers.multi_vector import (
    MultiVectorRetriever,
)
from packages.knowledge.retrievers.schemas import RetrievalRequest
from packages.knowledge.vectorstores.schema import SearchFilter, SearchResult


def _chunk(document_id, chunk_index: int, content: str, *, representation_type: str | None = None) -> DocumentChunk:
    return DocumentChunk(
        id=uuid4(),
        tenant_id=uuid4(),
        document_id=document_id,
        chunk_index=chunk_index,
        content=content,
        token_count=1,
        character_count=len(content),
        metadata_={"representation_type": representation_type} if representation_type else {},
    )


class _FakeInnerRetriever:
    def __init__(self, matches: list[SearchResult]) -> None:
        self._matches = matches

    async def retrieve(self, _request: RetrievalRequest) -> list[SearchResult]:
        return self._matches


class _FakeVectorStore:
    def __init__(self, similarity_results_by_document: dict[object, list[SearchResult]]) -> None:
        self._results = similarity_results_by_document
        self.received_document_ids: list[object] = []

    async def similarity_search(self, *, query_embedding, filters: SearchFilter, options=None):
        self.received_document_ids.append(filters.document_id)
        return self._results.get(filters.document_id, [])


def _request() -> RetrievalRequest:
    return RetrievalRequest(
        query_embedding=[0.1],
        filters=SearchFilter(tenant_id=uuid4(), model_profile_id=uuid4()),
        query="a real query",
    )


@pytest.mark.asyncio
async def test_non_summary_matches_pass_through_unchanged():
    document_id = uuid4()
    match = _chunk(document_id, 0, "an ordinary primary chunk")

    inner = _FakeInnerRetriever([SearchResult(chunk=match, score=0.5)])
    store = _FakeVectorStore({})
    retriever = MultiVectorRetriever(inner, store)

    results = await retriever.retrieve(_request())

    assert len(results) == 1
    assert results[0].chunk is match
    assert store.received_document_ids == []


@pytest.mark.asyncio
async def test_summary_hit_is_resolved_to_a_real_primary_chunk_not_returned_itself():
    document_id = uuid4()
    summary_match = _chunk(document_id, -1, "a synthetic document summary", representation_type="summary")
    real_chunk = _chunk(document_id, 0, "the real chunk content")

    inner = _FakeInnerRetriever([SearchResult(chunk=summary_match, score=0.9)])
    store = _FakeVectorStore({document_id: [SearchResult(chunk=real_chunk, score=0.8)]})
    retriever = MultiVectorRetriever(inner, store)

    results = await retriever.retrieve(_request())

    assert len(results) == 1
    assert results[0].chunk is real_chunk
    assert results[0].chunk.metadata_.get("representation_type") != "summary"


@pytest.mark.asyncio
async def test_summary_hit_with_no_resolvable_primary_content_yields_nothing():
    """
    If the scoped re-search only finds the summary chunk itself (an
    edge case, but possible for a document with no real primary
    chunks left, e.g. mid-reindex), it must not leak back out as
    literal context.
    """
    document_id = uuid4()
    summary_match = _chunk(document_id, -1, "a synthetic summary", representation_type="summary")

    inner = _FakeInnerRetriever([SearchResult(chunk=summary_match, score=0.9)])
    store = _FakeVectorStore(
        {document_id: [SearchResult(chunk=summary_match, score=0.9)]}
    )
    retriever = MultiVectorRetriever(inner, store)

    results = await retriever.retrieve(_request())

    assert results == []


@pytest.mark.asyncio
async def test_two_summary_hits_for_the_same_document_only_resolve_once():
    document_id = uuid4()
    summary_match = _chunk(document_id, -1, "summary", representation_type="summary")
    real_chunk = _chunk(document_id, 0, "real content")

    inner = _FakeInnerRetriever(
        [
            SearchResult(chunk=summary_match, score=0.9),
            SearchResult(chunk=summary_match, score=0.85),
        ]
    )
    store = _FakeVectorStore({document_id: [SearchResult(chunk=real_chunk, score=0.8)]})
    retriever = MultiVectorRetriever(inner, store)

    await retriever.retrieve(_request())

    assert store.received_document_ids == [document_id]


@pytest.mark.asyncio
async def test_a_chunk_matched_both_directly_and_via_summary_resolution_is_deduplicated():
    """
    The exact regression found live: a single-chunk document's real
    chunk was matched directly by the inner retriever *and*
    independently re-surfaced by resolving its own document's summary
    hit — without dedup, the same chunk came back twice at two
    different scores.
    """
    document_id = uuid4()
    real_chunk = _chunk(document_id, 0, "the one real chunk")
    summary_match = _chunk(document_id, -1, "summary", representation_type="summary")

    inner = _FakeInnerRetriever(
        [
            SearchResult(chunk=real_chunk, score=0.033),
            SearchResult(chunk=summary_match, score=0.9),
        ]
    )
    store = _FakeVectorStore({document_id: [SearchResult(chunk=real_chunk, score=0.683)]})
    retriever = MultiVectorRetriever(inner, store)

    results = await retriever.retrieve(_request())

    assert len(results) == 1
    # The higher of the two scores for the same chunk id is kept.
    assert results[0].score == 0.683
