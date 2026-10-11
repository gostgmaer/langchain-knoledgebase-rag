"""
WriterNode (packages/graph/nodes/writer.py) — output must satisfy the
same messages/usage/citations contract LLMNode already guarantees, so
ChatService._finalize_or_pause needs no changes to persist it. Real
PromptBuilder (pure, deterministic, no external deps); a fake inner
LLMChatService in place of a real LLM call.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from packages.application.services.platform_settings_service import default_value
from packages.chat.response import LLMChatResponse
from packages.graph.nodes import writer as writer_module
from packages.graph.nodes.writer import WriterNode
from packages.graph.schemas import ResearchFinding
from packages.knowledge.schemas import Citation
from packages.prompts.builder import PromptBuilder


class _FakePlatformSettings:
    async def get(self, key: str):
        return default_value(key)


def _prompt_builder() -> PromptBuilder:
    return PromptBuilder(_FakePlatformSettings())


class _FakeLLMChatService:
    def __init__(self, response: LLMChatResponse, chunks: list[str] | None = None) -> None:
        self._response = response
        self._chunks = chunks or []
        self.received_requests: list = []

    async def chat(self, request):
        self.received_requests.append(request)
        return self._response

    async def astream(self, request):
        self.received_requests.append(request)
        for piece in self._chunks:
            yield AIMessageChunk(content=piece)


def _findings() -> list[ResearchFinding]:
    return [
        ResearchFinding(
            sub_question="What does document A say about X?",
            finding="Document A says X is fast.",
            citations=[Citation(document_id=uuid4(), chunk_id=uuid4(), chunk_index=0, score=0.9)],
        ),
        ResearchFinding(
            sub_question="What does document B say about X?",
            finding="Document B says X is reliable.",
            citations=[Citation(document_id=uuid4(), chunk_id=uuid4(), chunk_index=0, score=0.8)],
        ),
    ]


def _state() -> dict:
    return {
        "conversation_id": uuid4(),
        "system_prompt": "You are a helpful assistant.",
        "messages": [HumanMessage(content="compare A and B on X")],
        "research_findings": _findings(),
    }


@pytest.mark.asyncio
async def test_output_satisfies_the_messages_usage_citations_contract():
    response = LLMChatResponse(
        message=AIMessage(content="A says X is fast; B says X is reliable."),
        usage={"input_tokens": 10, "output_tokens": 5},
    )
    chat_service = _FakeLLMChatService(response)
    node = WriterNode(chat_service, _prompt_builder())

    result = await node(_state())

    assert result["messages"][-1].content == "A says X is fast; B says X is reliable."
    assert result["usage"] == {"input_tokens": 10, "output_tokens": 5}
    assert len(result["citations"]) == 2


@pytest.mark.asyncio
async def test_no_tools_are_bound_for_pure_synthesis():
    response = LLMChatResponse(message=AIMessage(content="synthesized"))
    chat_service = _FakeLLMChatService(response)
    node = WriterNode(chat_service, _prompt_builder())

    await node(_state())

    assert chat_service.received_requests[0].tools == []


@pytest.mark.asyncio
async def test_citations_are_flattened_across_every_finding():
    response = LLMChatResponse(message=AIMessage(content="synthesized"))
    chat_service = _FakeLLMChatService(response)
    node = WriterNode(chat_service, _prompt_builder())

    findings = _findings()
    state = _state()
    state["research_findings"] = findings

    result = await node(state)

    all_citation_ids = {citation.chunk_id for finding in findings for citation in finding.citations}
    result_citation_ids = {citation.chunk_id for citation in result["citations"]}
    assert result_citation_ids == all_citation_ids


@pytest.mark.asyncio
async def test_the_same_chunk_cited_by_two_sub_questions_is_deduped_keeping_the_higher_score():
    """
    The exact bug reproduced live: a two-part question against a
    single-document knowledge base independently retrieved the same
    chunk for both sub-questions, with two different rerank scores —
    it must appear once in the final citations, at its higher score.
    """

    document_id = uuid4()
    chunk_id = uuid4()

    findings = [
        ResearchFinding(
            sub_question="What is the payload capacity?",
            finding="73 kilograms.",
            citations=[Citation(document_id=document_id, chunk_id=chunk_id, chunk_index=0, score=10.9)],
        ),
        ResearchFinding(
            sub_question="What is the flight endurance?",
            finding="51 minutes.",
            citations=[Citation(document_id=document_id, chunk_id=chunk_id, chunk_index=0, score=8.8)],
        ),
    ]

    response = LLMChatResponse(message=AIMessage(content="synthesized"))
    chat_service = _FakeLLMChatService(response)
    node = WriterNode(chat_service, _prompt_builder())

    state = _state()
    state["research_findings"] = findings

    result = await node(state)

    assert len(result["citations"]) == 1
    assert result["citations"][0].score == 10.9


@pytest.mark.asyncio
async def test_a_streaming_turn_pushes_tokens_instead_of_discarding_the_answer(monkeypatch):
    """
    docs/BUGS.md item 60 — ChatService.stream() (the endpoint the real UI
    calls) only ever sees events pushed through the graph's stream writer;
    it never reads a node's final state write directly. Before this test's
    fix, WriterNode always called the non-streaming self._chat.chat() no
    matter what state["stream"] said, so every multi-part/comparison turn
    pushed zero token events and ChatService.stream() replaced the (real,
    correct) synthesized answer with its generic empty-reply fallback.
    """

    pushed: list[dict] = []
    monkeypatch.setattr(writer_module, "get_stream_writer", lambda: pushed.append)

    response = LLMChatResponse(message=AIMessage(content="unused in the streaming path"))
    chat_service = _FakeLLMChatService(response, chunks=["A says X is fast; ", "B says X is reliable."])
    node = WriterNode(chat_service, _prompt_builder())

    state = _state()
    state["stream"] = True

    result = await node(state)

    assert result["messages"][-1].content == "A says X is fast; B says X is reliable."
    assert len(result["citations"]) == 2

    token_events = [event for event in pushed if event["type"] == "token"]
    assert [event["content"] for event in token_events] == ["A says X is fast; ", "B says X is reliable."]
    assert any(event["type"] == "citations" and len(event["citations"]) == 2 for event in pushed)
