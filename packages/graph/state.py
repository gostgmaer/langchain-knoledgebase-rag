from __future__ import annotations

import datetime
from typing import Annotated, Any
from uuid import UUID

from langgraph.graph.message import AnyMessage, add_messages
from typing_extensions import TypedDict

from packages.knowledge.schemas import Citation, SearchResult
from packages.memory.schemas import MemoryFact
from packages.planner.models import ExecutionPlan


def merge_usage(
    current: dict[str, Any] | None,
    update: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Reducer for `usage`: sums token counts across however many times
    the LLM node runs in a single turn (e.g. once before a tool call,
    once after) instead of the last call silently overwriting the
    first. Nodes should return only their own call's usage delta, not
    a pre-merged total — this function does the accumulation.

    `update=None` (as opposed to `update={}`) is a deliberate, explicit
    RESET signal — packages/application/services/chat_service.py's
    `_build_state()` passes it at the start of every new turn. This
    distinction matters because LangGraph's checkpointer persists
    `usage` across *every* invoke()/resume() call against the same
    thread_id, not just within one turn's own node executions —
    passing `{}` would merge as a pure no-op against whatever's
    already checkpointed from prior turns (every key still comes from
    `current` since `update` contributes nothing), so `usage` would
    silently accumulate for the conversation's entire lifetime instead
    of resetting per turn. Confirmed live: a long-lived test
    conversation (~100+ turns, reused throughout one session) grew
    input_tokens past Postgres INTEGER's 2^31 ceiling, crashing every
    subsequent message with a real DBAPIError on insert.

    LangChain's UsageMetadata has non-numeric sub-fields too (e.g.
    `input_token_details`), so only int/float values are summed —
    anything else falls back to the most recent value.
    """
    if update is None:
        return {}

    current = current or {}
    merged: dict[str, Any] = {}
    for key in set(current) | set(update):
        c, u = current.get(key), update.get(key)
        if isinstance(c, (int, float)) and isinstance(u, (int, float)):
            merged[key] = c + u
        else:
            merged[key] = u if key in update else c
    return merged


class GraphState(TypedDict, total=False):
    """
    Shared state across the LangGraph workflow.
    Every node reads from and writes to this state.
    """

    #
    # Conversation
    #
    response:str
    final_response: str | None
    messages: Annotated[list[AnyMessage], add_messages]

    conversation_id: UUID
    thread_id: UUID
    tenant_id: UUID
    user_id: UUID

    #
    # AI
    #

    model_profile_id: UUID
    system_prompt: str
    temperature: float
    max_tokens: int
    #
    # RAG
    #

    search_results: list[SearchResult]
    context: list[str]
    citations: list[Citation]
    rewritten_query: str | None
    expanded_queries: list[str]

    #
    # Tools
    #

    tool_calls: list[dict[str, Any]]
    tool_results: list[Any]

    #
    # Memory
    #
    memories: list[MemoryFact]
    memory_checkpoint_id: str | None
    memory_checkpoint_version: int
    summary: str
    conversation_summary: str | None
    memory_context: str | None
    user_preferences: dict[str, Any]
    user_facts: list[str]
    created_at: datetime
    updated_at: datetime
    #
    # Execution
    #
    execution_plan: ExecutionPlan
    retrieval_enabled: bool
    tools_enabled: bool
    stream: bool
    next_node: str
    metadata: dict[str, object]
    usage: Annotated[dict[str, int], merge_usage]

    #
    # Error Handling
    #

    retry_count: int
    error: str | None
    last_error: str | None
    error_node: str | None

