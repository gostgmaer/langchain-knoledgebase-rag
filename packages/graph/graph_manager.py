# Graph manager
from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage

from packages.chat.chat_service import ChatService
from packages.graph.builder import GraphBuilder


class GraphManager:
    """
    Singleton manager responsible for:

    - Building the graph
    - Compiling the graph
    - Invoking the graph
    - Streaming graph execution
    """

    def __init__(
        self,
        chat_service: ChatService,
    ) -> None:

        self._graph = GraphBuilder(
            chat_service=chat_service,
        ).build()

    async def ainvoke(
        self,
        message: str,
        **kwargs: Any,
    ) -> dict[str, Any]:

        state = {
            "messages": [
                HumanMessage(content=message),
            ],
            "session_id": kwargs.get("session_id"),
            "conversation_id": kwargs.get("conversation_id"),
            "agent_id": kwargs.get("agent_id"),
            "metadata": kwargs.get("metadata", {}),
        }

        result = await self._graph.ainvoke(
            state,
            config={
                "configurable": {
                    "thread_id": session_id,
                }
            },
        )

    async def astream(
        self,
        message: str,
        **kwargs: Any,
    ):
        state = {
            "messages": [
                HumanMessage(content=message),
            ],
            "session_id": kwargs.get("session_id"),
            "conversation_id": kwargs.get("conversation_id"),
            "agent_id": kwargs.get("agent_id"),
            "metadata": kwargs.get("metadata", {}),
        }

        async for event in self._graph.astream(state):
            yield event
