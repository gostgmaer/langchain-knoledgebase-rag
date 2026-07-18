# Agent node
from __future__ import annotations

from langchain_core.messages import AIMessage

from packages.chat.chat_service import ChatService
from packages.graph.state import AgentState

class AgentNode:
    """
    Primary LLM execution node.

    Responsibilities:
    - Read conversation messages
    - Invoke ChatService
    - Append assistant response
    - Return updated state

    This node must remain provider-agnostic.
    """

    def __init__(
        self,
        chat_service: ChatService,
    ) -> None:
        self._chat = chat_service

    async def __call__(
        self,
        state: AgentState,
    ) -> AgentState:

        response = await self._chat.ainvoke(
            messages=state["messages"],
        )

        return {
            "messages": [
                AIMessage(content=response.content)
            ]
        }