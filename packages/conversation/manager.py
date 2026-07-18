# Conversation manager
from __future__ import annotations

from langchain_core.messages import HumanMessage

from packages.conversation.store import ConversationStore
from packages.graph.graph_manager import GraphManager
from packages.graph.state import AgentState


class ConversationManager:

    def __init__(
        self,
        graph: GraphManager,
        store: ConversationStore,
    ) -> None:
        self._graph = graph
        self._store = store

    async def chat(
        self,
        session_id: str,
        message: str,
    ) -> AgentState:

        state = await self._store.load(session_id)

        if state is None:
            state = {
                "messages": [],
                "session_id": session_id,
                "conversation_id": None,
                "agent_id": None,
                "metadata": {},
            }

        state["messages"].append(
            HumanMessage(content=message)
        )

        state = await self._graph.ainvoke(state)

        await self._store.save(state)

        return state