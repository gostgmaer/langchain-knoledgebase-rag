from __future__ import annotations

import datetime
from typing import Any

from uuid import UUID
from langchain_core.messages import BaseMessage
from langgraph.graph.message import AnyMessage, add_messages
from typing_extensions import Annotated, TypedDict
from packages.planner.models import ExecutionPlan

from packages.knowledge.schemas import SearchResult
from packages.memory.schemas import MemoryFact
from packages.rag.schemas import Citation

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
    usage: dict[str, Any]

    #
    # Error Handling
    #

    retry_count: int
    error: str | None
    last_error: str | None
    error_node: str | None

