"""
ParentDocumentRetriever (packages/knowledge/retrievers/providers/
parent_document.py) — pure logic tests against a fake inner retriever
and a fake vector store, no real DB/Chroma. Live-verified separately
against a real multi-chunk section (a query matching only one
paragraph's fragment correctly returned the whole section, reassembled
from its sibling chunks) — these tests pin down the surrounding logic:
dedup, no-section passthrough, empty-siblings fallback, sort order.
"""

from uuid import uuid4

import pytest

from packages.domain.models.document_chunk import DocumentChunk
from packages.knowledge.retrievers.providers.parent_document import (
    ParentDocumentRetriever,
)
from packages.knowledge.retrievers.schemas import RetrievalRequest
from packages.knowledge.vectorstores.schema import SearchFilter, SearchResult


def _chunk(document_id, chunk_index: int, section: str | None, content: str) -> DocumentChunk:
    return DocumentChunk(
        id=uuid4(),
        tenant_id=uuid4(),
        document_id=document_id,
        chunk_index=chunk_index,
        section=section,
        content=content,
        token_count=1,
        character_count=len(content),
    )


class _FakeInnerRetriever:
    def __init__(self, matches: list[SearchResult]) -> None:
        self._matches = matches

    async def retrieve(self, _request: RetrievalRequest) -> list[SearchResult]:
        return self._matches


class _FakeVectorStore:
    def __init__(self, siblings_by_section: dict[str, list[SearchResult]]) -> None:
        self._siblings_by_section = siblings_by_section
        self.received_filters: list[SearchFilter] = []

    async def list_chunks(self, *, filters: SearchFilter, limit: int = 500) -> list[SearchResult]:
        self.received_filters.append(filters)
        return self._siblings_by_section.get(filters.metadata.get("section"), [])


def _request() -> RetrievalRequest:
    return RetrievalRequest(
        query_embedding=[0.1],
        filters=SearchFilter(tenant_id=uuid4(), model_profile_id=uuid4()),
        query="a real query",
    )


@pytest.mark.asyncio
async def test_reassembles_sibling_chunks_in_chunk_index_order():
    document_id = uuid4()
    matched_fragment = _chunk(document_id, 1, "Technical Details", "middle paragraph")

    siblings = [
        _chunk(document_id, 2, "Technical Details", "last paragraph"),
        _chunk(document_id, 0, "Technical Details", "first paragraph"),
        _chunk(document_id, 1, "Technical Details", "middle paragraph"),
    ]

    inner = _FakeInnerRetriever([SearchResult(chunk=matched_fragment, score=0.9)])
    store = _FakeVectorStore(
        {"Technical Details": [SearchResult(chunk=c, score=0.0) for c in siblings]}
    )
    retriever = ParentDocumentRetriever(inner, store)

    results = await retriever.retrieve(_request())

    assert len(results) == 1
    assert results[0].chunk.content == "first paragraph\n\nmiddle paragraph\n\nlast paragraph"
    # The original best-match score is preserved, not the sibling scores.
    assert results[0].score == 0.9


@pytest.mark.asyncio
async def test_chunk_with_no_section_is_returned_unchanged():
    document_id = uuid4()
    match = _chunk(document_id, 0, None, "a plain-text chunk with no headers")

    inner = _FakeInnerRetriever([SearchResult(chunk=match, score=0.7)])
    store = _FakeVectorStore({})
    retriever = ParentDocumentRetriever(inner, store)

    results = await retriever.retrieve(_request())

    assert len(results) == 1
    assert results[0].chunk is match
    assert store.received_filters == []


@pytest.mark.asyncio
async def test_two_matches_from_the_same_parent_section_deduplicate_to_one_result():
    document_id = uuid4()
    match_a = _chunk(document_id, 0, "Overview", "fragment A")
    match_b = _chunk(document_id, 1, "Overview", "fragment B")

    inner = _FakeInnerRetriever(
        [
            SearchResult(chunk=match_a, score=0.9),
            SearchResult(chunk=match_b, score=0.8),
        ]
    )
    store = _FakeVectorStore(
        {
            "Overview": [
                SearchResult(chunk=match_a, score=0.0),
                SearchResult(chunk=match_b, score=0.0),
            ]
        }
    )
    retriever = ParentDocumentRetriever(inner, store)

    results = await retriever.retrieve(_request())

    assert len(results) == 1


@pytest.mark.asyncio
async def test_matches_from_different_sections_both_kept():
    document_id = uuid4()
    match_a = _chunk(document_id, 0, "Overview", "overview text")
    match_b = _chunk(document_id, 5, "Conclusion", "conclusion text")

    inner = _FakeInnerRetriever(
        [
            SearchResult(chunk=match_a, score=0.9),
            SearchResult(chunk=match_b, score=0.8),
        ]
    )
    store = _FakeVectorStore(
        {
            "Overview": [SearchResult(chunk=match_a, score=0.0)],
            "Conclusion": [SearchResult(chunk=match_b, score=0.0)],
        }
    )
    retriever = ParentDocumentRetriever(inner, store)

    results = await retriever.retrieve(_request())

    sections = {r.chunk.section for r in results}
    assert sections == {"Overview", "Conclusion"}


@pytest.mark.asyncio
async def test_empty_sibling_lookup_falls_back_to_the_original_match():
    """
    Guards against a real edge case: a section value that no longer
    resolves to anything (e.g. a race with a concurrent delete/reindex)
    shouldn't drop the match entirely — return what was actually found.
    """
    document_id = uuid4()
    match = _chunk(document_id, 0, "Ghost Section", "a match with no findable siblings")

    inner = _FakeInnerRetriever([SearchResult(chunk=match, score=0.5)])
    store = _FakeVectorStore({})
    retriever = ParentDocumentRetriever(inner, store)

    results = await retriever.retrieve(_request())

    assert len(results) == 1
    assert results[0].chunk is match
