# Graph state
from __future__ import annotations

from typing import Annotated, Any

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """
    Runtime state shared across the LangGraph workflow.

    This state is intentionally provider-agnostic and persistence-agnostic.
    Additional fields can be introduced over time without breaking existing
    graph nodes.
    """

    # Conversation history
    messages: Annotated[list[AnyMessage], add_messages]

    # Runtime identifiers
    session_id: str | None
    conversation_id: str | None
    agent_id: str | None

    # Runtime metadata
    metadata: dict[str, Any]