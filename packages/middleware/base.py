from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from packages.graph.state import GraphState


class Middleware(ABC):

    async def before(
        self,
        state: GraphState,
    ) -> GraphState:
        return state

    async def after(
        self,
        state: GraphState,
    ) -> GraphState:
        return state