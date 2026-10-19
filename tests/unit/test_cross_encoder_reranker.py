"""
docs/BUGS.md item 57: CrossEncoderReranker._get_model() lazy-loads the
underlying sentence-transformers model from several real OS threads at
once (ResearcherNode fans out rerank() calls over sub-questions via
asyncio.to_thread) — these tests prove the model is only ever
constructed once under real concurrent load, and that rerank() still
returns correct, non-empty results while that's happening.
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

from packages.knowledge.reranking.cross_encoder import CrossEncoderReranker
from packages.knowledge.vectorstores.schema import SearchResult


def _fake_result(content: str) -> SearchResult:
    return SearchResult(chunk=SimpleNamespace(content=content), score=0.0)


@pytest.fixture
def fake_cross_encoder_module(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """
    Stands in for `sentence_transformers`, so these tests never need the
    real ~90MB model or any network/disk access. The fake constructor
    sleeps briefly to widen the race window a real, slow model load
    would have, and counts how many times it's actually called.
    """

    construct_calls = []

    class FakeCrossEncoder:
        def __init__(self, model_name: str) -> None:
            construct_calls.append((model_name, threading.get_ident()))
            time.sleep(0.05)

        def predict(self, pairs):
            # Score by input order, descending, so the test can assert
            # on a deterministic ranking.
            return list(range(len(pairs), 0, -1))

    fake_module = ModuleType("sentence_transformers")
    fake_module.CrossEncoder = FakeCrossEncoder
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    constructor_calls = MagicMock()
    constructor_calls.calls = construct_calls
    return constructor_calls


@pytest.mark.asyncio
async def test_concurrent_first_use_constructs_the_model_exactly_once(
    fake_cross_encoder_module: MagicMock,
) -> None:
    reranker = CrossEncoderReranker()
    results = [_fake_result(f"chunk {i}") for i in range(3)]

    # Mirrors ResearcherNode.__call__'s asyncio.gather fan-out: several
    # independent rerank() calls in flight at once, the exact shape
    # that reaches _get_model() from multiple real threads.
    await asyncio.gather(
        *(reranker.rerank(f"query {i}", results, top_k=2) for i in range(5))
    )

    assert len(fake_cross_encoder_module.calls) == 1, (
        "the model should be constructed exactly once even when 5 rerank() "
        f"calls race to be first; got {len(fake_cross_encoder_module.calls)} "
        "constructions"
    )


@pytest.mark.asyncio
async def test_concurrent_reranking_still_returns_correct_results(
    fake_cross_encoder_module: MagicMock,
) -> None:
    reranker = CrossEncoderReranker()
    results = [_fake_result(f"chunk {i}") for i in range(3)]

    outcomes = await asyncio.gather(
        *(reranker.rerank(f"query {i}", results, top_k=2) for i in range(5))
    )

    for ranked in outcomes:
        assert len(ranked) == 2
        assert all(isinstance(r, SearchResult) for r in ranked)
        # FakeCrossEncoder scores strictly descending by input order, so
        # the top-2 after sorting-by-score-descending is deterministic.
        assert [r.chunk.content for r in ranked] == ["chunk 0", "chunk 1"]


@pytest.mark.asyncio
async def test_empty_results_short_circuit_without_touching_the_model(
    fake_cross_encoder_module: MagicMock,
) -> None:
    reranker = CrossEncoderReranker()

    ranked = await reranker.rerank("query", [], top_k=5)

    assert ranked == []
    assert len(fake_cross_encoder_module.calls) == 0
