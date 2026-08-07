"""
GraphExtractor (packages/knowledge/extraction/graph_extractor.py) —
fails open on any LLM error, same idiom SelfQueryRetriever/QueryAnalyzer
already use. No real LLM call; a fake with_structured_output chain.
"""

from __future__ import annotations

import pytest

from packages.knowledge.extraction.graph_extractor import (
    ExtractedEntity,
    ExtractedRelationship,
    GraphExtraction,
    GraphExtractor,
)


class _Doc:
    def __init__(self, content: str) -> None:
        self.page_content = content


class _FakeChain:
    def __init__(self, *, result=None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.calls: list[str] = []

    async def ainvoke(self, prompt: str):
        self.calls.append(prompt)
        if self._error is not None:
            raise self._error
        return self._result


class _FakeLLM:
    def __init__(self, chain: _FakeChain) -> None:
        self._chain = chain

    def with_structured_output(self, _schema):
        return self._chain


@pytest.mark.asyncio
async def test_empty_documents_returns_empty_extraction_without_calling_the_llm():
    chain = _FakeChain(result=GraphExtraction())
    extractor = GraphExtractor(_FakeLLM(chain))

    result = await extractor.extract([])

    assert result == GraphExtraction()
    assert chain.calls == []


@pytest.mark.asyncio
async def test_llm_error_fails_open_to_an_empty_extraction():
    chain = _FakeChain(error=RuntimeError("provider down"))
    extractor = GraphExtractor(_FakeLLM(chain))

    result = await extractor.extract([_Doc("Acme Corp acquired Widget Inc.")])

    assert result == GraphExtraction()


@pytest.mark.asyncio
async def test_successful_extraction_is_returned_unchanged():
    extraction = GraphExtraction(
        entities=[ExtractedEntity(name="Acme Corp", entity_type="organization")],
        relationships=[
            ExtractedRelationship(source="Acme Corp", target="Widget Inc", relationship_type="acquired")
        ],
    )
    chain = _FakeChain(result=extraction)
    extractor = GraphExtractor(_FakeLLM(chain))

    result = await extractor.extract([_Doc("Acme Corp acquired Widget Inc.")])

    assert result is extraction


@pytest.mark.asyncio
async def test_source_excerpt_is_bounded_to_the_char_limit():
    chain = _FakeChain(result=GraphExtraction())
    extractor = GraphExtractor(_FakeLLM(chain))

    huge_doc = _Doc("x" * 20_000)
    await extractor.extract([huge_doc])

    # The excerpt is embedded in the prompt string alongside fixed
    # instruction text, so just assert it didn't pass the raw 20k
    # characters through unbounded.
    assert len(chain.calls[0]) < 10_000
