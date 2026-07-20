"""
packages/middleware.py

Simple middleware abstraction for the AI Platform.

Middlewares execute:
    before() -> before the graph starts
    after()  -> after the graph completes

Execution order:

before():
    M1 -> M2 -> M3

Graph

after():
    M3 -> M2 -> M1
"""

from __future__ import annotations

from abc import ABC

from packages.graph.state import GraphState


class Middleware(ABC):
    """
    Base middleware.

    Override only the methods you need.
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