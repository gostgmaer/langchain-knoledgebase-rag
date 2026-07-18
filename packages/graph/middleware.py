# Graph middleware
from __future__ import annotations

from typing import Awaitable, Callable

from packages.graph.state import GraphState


NodeCallable = Callable[[GraphState], Awaitable[GraphState]]


class GraphMiddleware:
    """
    Base middleware.
    """

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


class LoggingMiddleware(GraphMiddleware):

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


class MetricsMiddleware(GraphMiddleware):

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


class MiddlewarePipeline:

    def __init__(
        self,
        *middlewares: GraphMiddleware,
    ):
        self.middlewares = middlewares

    async def before(
        self,
        state: GraphState,
    ):
        for middleware in self.middlewares:
            state = await middleware.before(state)

        return state

    async def after(
        self,
        state: GraphState,
    ):
        for middleware in reversed(self.middlewares):
            state = await middleware.after(state)

        return state