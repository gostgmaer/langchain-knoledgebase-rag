"""
HybridRetriever (packages/knowledge/retrievers/providers/hybrid.py) — pure logic tests against a
fake vector store, no real DB/Chroma.
"""

from uuid import uuid4

import pytest

from packages.domain.models.document_chunk import DocumentChunk
from packages.knowledge.retrievers.providers.hybrid import HybridRetriever
from packages.knowledge.retrievers.schemas import RetrievalRequest
from packages.knowledge.vectorstores.schema import SearchFilter, SearchOptions, SearchResult


def _chunk(content: str) -> DocumentChunk:
    return DocumentChunk(
        id=uuid4(),
        tenant_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        content=content,
        token_count=1,
        character_count=len(content),
    )


class _FakeVectorStore:
    def __init__(self, vector_results: list[SearchResult], candidates: list[SearchResult]) -> None:
        self._vector_results = vector_results
        self._candidates = candidates

    async def similarity_search(self, *, query_embedding, filters, options=None):
        return self._vector_results

    async def list_chunks(self, *, filters, limit):
        return self._candidates


class _FakePlatformSettings:
    async def get(self, key: str):
        assert key == "retrieval_keyword_weight"
        return 1.0


def _request(query: str) -> RetrievalRequest:
    return RetrievalRequest(
        query_embedding=[0.1],
        filters=SearchFilter(tenant_id=uuid4(), model_profile_id=uuid4()),
        query=query,
        options=SearchOptions(limit=5),
    )


@pytest.mark.asyncio
async def test_a_candidate_pool_with_no_matchable_terms_falls_back_to_vector_only():
    """
    Every candidate here is pure Japanese text — _tokenize's [a-z0-9] pattern matches none of it,
    so the BM25 corpus is entirely empty documents. BM25Okapi itself divides by the corpus's
    average document length while indexing with no guard of its own, so this used to raise a bare
    ZeroDivisionError instead of just falling back to the vector ranking, taking down every hybrid
    (the default strategy) chat/search call for a tenant whose content is in a non-Latin script.
    """
    chunk = _chunk("これは日本語のテキストです")
    vector_result = SearchResult(chunk=chunk, score=0.9)

    store = _FakeVectorStore(
        vector_results=[vector_result],
        candidates=[vector_result],
    )
    retriever = HybridRetriever(vector_store=store, platform_settings=_FakePlatformSettings())

    results = await retriever.retrieve(_request("これは質問です"))

    assert [r.chunk.id for r in results] == [chunk.id]


@pytest.mark.asyncio
async def test_a_mixed_pool_with_some_matchable_terms_still_ranks_by_keyword():
    matching_chunk = _chunk("the quick brown fox")
    nonmatching_chunk = _chunk("これは日本語のテキストです")
    vector_results = [
        SearchResult(chunk=nonmatching_chunk, score=0.95),
        SearchResult(chunk=matching_chunk, score=0.5),
    ]

    store = _FakeVectorStore(vector_results=vector_results, candidates=vector_results)
    retriever = HybridRetriever(vector_store=store, platform_settings=_FakePlatformSettings())

    results = await retriever.retrieve(_request("fox"))

    assert matching_chunk.id in [r.chunk.id for r in results]
