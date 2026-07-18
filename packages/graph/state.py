from __future__ import annotations

from typing import Any

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict


class GraphState(TypedDict, total=False):
    """
    Shared state across the LangGraph workflow.
    Every node reads from and writes to this state.
    """

    #
    # Conversation
    #

    messages: Annotated[list[BaseMessage], add_messages]

    conversation_id: str
    thread_id: str
    tenant_id: str
    user_id: str

    #
    # AI
    #

    model: str
    system_prompt: str

    #
    # RAG
    #

    documents: list[Document]

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

    next_node: str
    metadata: dict[str, Any]
    usage: dict[str, Any]

    #
    # Error Handling
    #

    retry_count: int
    error: str | None
