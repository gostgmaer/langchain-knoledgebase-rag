from __future__ import annotations

from abc import ABC, abstractmethod

from packages.graph.state import AgentState


class ConversationStore(ABC):
    """Persistence abstraction for conversation state."""

    @abstractmethod
    async def load(
        self,
        session_id: str,
    ) -> AgentState | None:
        ...

    @abstractmethod
    async def save(
        self,
        state: AgentState,
    ) -> None:
        ...

    @abstractmethod
    async def delete(
        self,
        session_id: str,
    ) -> None:
        ...