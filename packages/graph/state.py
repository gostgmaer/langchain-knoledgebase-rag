from __future__ import annotations

from typing import Any

from uuid import UUID
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict
from packages.knowledge.schemas import SearchResult
from packages.rag.schemas import Context
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
    messages: Annotated[list[BaseMessage], add_messages]

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
    context: Context | None
    citations: list[Citation]

    #
    # Tools
    #

    tool_calls: list[dict[str, Any]]
    tool_results: list[Any]

    #
    # Memory
    #

    summary: str

    #
    # Execution
    #
    retrieval_enabled: bool
    tools_enabled: bool
    stream: bool
    next_step: str
    metadata: dict[str, Any]
    usage: dict[str, Any]

    #
    # Error Handling
    #

    retry_count: int
    error: str | None

