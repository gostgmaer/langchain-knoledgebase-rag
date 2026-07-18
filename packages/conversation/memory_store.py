from __future__ import annotations

from packages.conversation.store import ConversationStore
from packages.graph.state import AgentState


class MemoryConversationStore(ConversationStore):

    def __init__(self) -> None:
        self._sessions: dict[str, AgentState] = {}

    async def load(
        self,
        session_id: str,
    ) -> AgentState | None:
        return self._sessions.get(session_id)

    async def save(
        self,
        state: AgentState,
    ) -> None:
        self._sessions[state["session_id"]] = state

    async def delete(
        self,
        session_id: str,
    ) -> None:
        self._sessions.pop(session_id, None)