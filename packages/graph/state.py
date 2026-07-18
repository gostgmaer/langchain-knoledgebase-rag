from __future__ import annotations

from typing import Any
from typing_extensions import TypedDict

from langchain_core.documents import Document

from packages.graph.types import Messages


class GraphState(TypedDict, total=False):
    """
    Shared state across every node.
    """

    messages: Messages

    documents: list[Document]

    tools: list[dict[str, Any]]

    user_id: str

    conversation_id: str

    thread_id: str

    system_prompt: str

    summary: str

    metadata: dict[str, Any]