"""
SelfQueryRetriever (packages/knowledge/retrievers/providers/self_query.py)
— pure logic tests against a fake inner retriever and a fake LLM chain,
no real DB/Chroma/network. The live-verified case this guards against:
a real run against Chroma initially returned zero results because the
LLM extracted a lowercase section name ("specifications") that didn't
exact-match the real, original-case stored heading ("Specifications")
— fixed via a `section_lower` shadow field, asserted here directly.
"""

from uuid import uuid4

import pytest

from packages.knowledge.retrievers.providers.self_query import (
    SelfQueryFilters,
    SelfQueryRetriever,
)
from packages.knowledge.retrievers.schemas import RetrievalRequest
from packages.knowledge.vectorstores.schema import SearchFilter


class _FakeChain:
    def __init__(self, result: SelfQueryFilters | Exception) -> None:
        self._result = result

    async def ainvoke(self, _prompt: str) -> SelfQueryFilters:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class _FakeLLM:
    def __init__(self, result: SelfQueryFilters | Exception) -> None:
        self._result = result

    def with_structured_output(self, _schema):
        return _FakeChain(self._result)


class _FakeInnerRetriever:
    def __init__(self) -> None:
        self.received_requests: list[RetrievalRequest] = []

    async def retrieve(self, request: RetrievalRequest) -> list:
        self.received_requests.append(request)
        return ["fake-result"]


def _request(query: str) -> RetrievalRequest:
    return RetrievalRequest(
        query_embedding=[0.1, 0.2],
        filters=SearchFilter(tenant_id=uuid4(), model_profile_id=uuid4()),
        query=query,
    )


@pytest.mark.asyncio
async def test_extracted_section_is_lowercased_into_section_lower_filter():
    """
    The exact regression: the LLM extracts natural-language casing
    ("specifications"), but Chroma's `where` equality is case-sensitive
    exact-match against the real stored heading ("Specifications").
    """
    inner = _FakeInnerRetriever()
    original_filters = SearchFilter(tenant_id=uuid4(), model_profile_id=uuid4())
    request = RetrievalRequest(
        query_embedding=[0.1, 0.2],
        filters=original_filters,
        query="what does the specifications section say",
    )
    retriever = SelfQueryRetriever(
        inner,
        _FakeLLM(SelfQueryFilters(section="specifications", page_number=None)),
    )

    await retriever.retrieve(request)

    assert len(inner.received_requests) == 1
    forwarded_filters = inner.received_requests[0].filters
    assert forwarded_filters.metadata == {"section_lower": "specifications"}
    # dataclasses.replace() builds a new object — the caller's original
    # filters must be left untouched, not mutated in place.
    assert original_filters.metadata == {}


@pytest.mark.asyncio
async def test_page_number_filter_is_forwarded_as_is():
    inner = _FakeInnerRetriever()
    retriever = SelfQueryRetriever(
        inner,
        _FakeLLM(SelfQueryFilters(section=None, page_number=3)),
    )

    await retriever.retrieve(_request("what's on page 3"))

    assert inner.received_requests[0].filters.metadata == {"page_number": 3}


@pytest.mark.asyncio
async def test_no_extractable_filters_delegates_unmodified():
    inner = _FakeInnerRetriever()
    original_filters = SearchFilter(tenant_id=uuid4(), model_profile_id=uuid4())
    retriever = SelfQueryRetriever(
        inner,
        _FakeLLM(SelfQueryFilters(section=None, page_number=None)),
    )

    request = RetrievalRequest(
        query_embedding=[0.1],
        filters=original_filters,
        query="tell me about this document",
    )
    await retriever.retrieve(request)

    assert inner.received_requests[0].filters is original_filters


@pytest.mark.asyncio
async def test_llm_failure_fails_open_to_the_inner_retriever_unmodified():
    """
    Same fail-open idiom as GraphPlanner's fallback to keyword matching
    — a classifier hiccup should never crash a turn.
    """
    inner = _FakeInnerRetriever()
    original_filters = SearchFilter(tenant_id=uuid4(), model_profile_id=uuid4())
    retriever = SelfQueryRetriever(inner, _FakeLLM(RuntimeError("LLM is down")))

    request = RetrievalRequest(
        query_embedding=[0.1],
        filters=original_filters,
        query="a real query",
    )
    result = await retriever.retrieve(request)

    assert result == ["fake-result"]
    assert inner.received_requests[0].filters is original_filters


@pytest.mark.asyncio
async def test_empty_query_skips_the_llm_call_entirely():
    inner = _FakeInnerRetriever()
    retriever = SelfQueryRetriever(
        inner,
        _FakeLLM(RuntimeError("should never be called")),
    )

    request = RetrievalRequest(
        query_embedding=[0.1],
        filters=SearchFilter(tenant_id=uuid4(), model_profile_id=uuid4()),
        query="   ",
    )
    result = await retriever.retrieve(request)

    assert result == ["fake-result"]


@pytest.mark.asyncio
async def test_extracted_filters_merge_with_existing_filters_not_replace_them():
    inner = _FakeInnerRetriever()
    retriever = SelfQueryRetriever(
        inner,
        _FakeLLM(SelfQueryFilters(section="introduction", page_number=None)),
    )

    request = RetrievalRequest(
        query_embedding=[0.1],
        filters=SearchFilter(
            tenant_id=uuid4(),
            model_profile_id=uuid4(),
            metadata={"pre_existing_key": "pre_existing_value"},
        ),
        query="what does the introduction say",
    )
    await retriever.retrieve(request)

    forwarded = inner.received_requests[0].filters.metadata
    assert forwarded == {
        "pre_existing_key": "pre_existing_value",
        "section_lower": "introduction",
    }
