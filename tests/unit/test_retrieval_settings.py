from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from packages.api.routers.retrieval_settings import RetrievalSettingsUpdateSchema
from packages.application.services.retrieval_settings_service import (
    RetrievalOverrides,
    RetrievalSettingsService,
    merge,
    platform_defaults,
)
from packages.graph.nodes.retrieve import RetrieveNode


def test_unset_overrides_use_the_platform_defaults():
    assert merge(RetrievalOverrides()) == platform_defaults()


def test_overrides_replace_only_what_they_set():
    effective = merge(RetrievalOverrides(max_results=9, reranking_enabled=False))
    assert effective.max_results == 9
    assert effective.reranking_enabled is False
    assert effective.min_relevance_score == platform_defaults().min_relevance_score


@pytest.mark.parametrize("field,value", [("max_results", 0), ("max_results", 21), ("min_relevance_score", 11)])
def test_out_of_range_values_are_rejected(field, value):
    with pytest.raises(ValidationError):
        RetrievalSettingsUpdateSchema(**{field: value})


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        RetrievalSettingsUpdateSchema(top_k=3)


@pytest.mark.asyncio
async def test_a_settings_read_failure_falls_back_to_defaults_instead_of_breaking_answers():
    class Broken:
        async def __aenter__(self):
            raise RuntimeError("db down")

        async def __aexit__(self, *exc):
            return False

    service = RetrievalSettingsService(lambda: Broken())
    assert await service.get_effective(uuid4()) == platform_defaults()


def _result(i, score):
    chunk = SimpleNamespace(id=uuid4(), document_id=uuid4(), chunk_index=i, content=f"c{i}")
    return SimpleNamespace(chunk=chunk, score=score, vector_score=None, keyword_score=None)


def _node(config):
    results = [_result(i, s) for i, s in enumerate([0.03, 0.02, 0.05, 0.01])]
    knowledge = SimpleNamespace(search=AsyncMock(return_value=results))
    reranker = SimpleNamespace(rerank=AsyncMock(return_value=[]), _model_name="m")
    settings_service = SimpleNamespace(get_effective=AsyncMock(return_value=config))
    return RetrieveNode(knowledge, reranker, None, settings_service), reranker, results


def _state():
    from langchain_core.messages import HumanMessage

    return {"messages": [HumanMessage(content="q")], "tenant_id": uuid4(), "model_profile_id": uuid4()}


@pytest.mark.asyncio
async def test_with_reranking_off_the_reranker_is_skipped_and_top_k_is_honoured():
    from packages.application.services.retrieval_settings_service import EffectiveRetrievalSettings

    node, reranker, results = _node(EffectiveRetrievalSettings(max_results=2, min_relevance_score=0.0, reranking_enabled=False))

    state = await node(_state())

    reranker.rerank.assert_not_awaited()
    assert len(state["context"]) == 2
    assert state["context"] == ["c2", "c0"]  # the two best by search score


@pytest.mark.asyncio
async def test_with_reranking_on_the_configured_top_k_reaches_the_reranker():
    from packages.application.services.retrieval_settings_service import EffectiveRetrievalSettings

    node, reranker, _ = _node(EffectiveRetrievalSettings(max_results=7, min_relevance_score=0.0, reranking_enabled=True))

    await node(_state())

    assert reranker.rerank.await_args.kwargs["top_k"] == 7
