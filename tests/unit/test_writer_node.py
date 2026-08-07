"""
WriterNode (packages/graph/nodes/writer.py) — output must satisfy the
same messages/usage/citations contract LLMNode already guarantees, so
ChatService._finalize_or_pause needs no changes to persist it. Real
PromptBuilder (pure, deterministic, no external deps); a fake inner
ChatService in place of a real LLM call.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from packages.chat.response import ChatResponse
from packages.graph.nodes.writer import WriterNode
from packages.graph.schemas import ResearchFinding
from packages.knowledge.schemas import Citation
from packages.prompts.builder import PromptBuilder


class _FakeChatService:
    def __init__(self, response: ChatResponse) -> None:
        self._response = response
        self.received_requests: list = []

    async def chat(self, request):
        self.received_requests.append(request)
        return self._response


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
    response = ChatResponse(
        message=AIMessage(content="A says X is fast; B says X is reliable."),
        usage={"input_tokens": 10, "output_tokens": 5},
    )
    chat_service = _FakeChatService(response)
    node = WriterNode(chat_service, PromptBuilder())

    result = await node(_state())

    assert result["messages"][-1].content == "A says X is fast; B says X is reliable."
    assert result["usage"] == {"input_tokens": 10, "output_tokens": 5}
    assert len(result["citations"]) == 2


@pytest.mark.asyncio
async def test_no_tools_are_bound_for_pure_synthesis():
    response = ChatResponse(message=AIMessage(content="synthesized"))
    chat_service = _FakeChatService(response)
    node = WriterNode(chat_service, PromptBuilder())

    await node(_state())

    assert chat_service.received_requests[0].tools == []


@pytest.mark.asyncio
async def test_citations_are_flattened_across_every_finding():
    response = ChatResponse(message=AIMessage(content="synthesized"))
    chat_service = _FakeChatService(response)
    node = WriterNode(chat_service, PromptBuilder())

    findings = _findings()
    state = _state()
    state["research_findings"] = findings

    result = await node(state)

    all_citation_ids = {citation.chunk_id for finding in findings for citation in finding.citations}
    result_citation_ids = {citation.chunk_id for citation in result["citations"]}
    assert result_citation_ids == all_citation_ids
