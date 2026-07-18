# Graph constants
from __future__ import annotations

from enum import StrEnum


class GraphNode(StrEnum):
    RETRIEVE = "retrieve"
    TOOL = "tool"
    LLM = "llm"
    SUMMARIZE = "summarize"


class GraphStateKey(StrEnum):
    MESSAGES = "messages"
    DOCUMENTS = "documents"
    TOOLS = "tools"
    SUMMARY = "summary"
    METADATA = "metadata"
    SYSTEM_PROMPT = "system_prompt"
    USER_ID = "user_id"
    CONVERSATION_ID = "conversation_id"
    THREAD_ID = "thread_id"