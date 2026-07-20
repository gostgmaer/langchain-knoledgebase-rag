from __future__ import annotations

from typing import Any

from packages.graph.builder import GraphBuilder
from packages.graph.state import GraphState


class GraphManager:

    def __init__(
        self,
        builder: GraphBuilder,
    ) -> None:

        self.graph = builder.build()

    def _config(
        self,
        state: GraphState,
    ) -> dict[str, Any]:

        return {
            "configurable": {
                "thread_id": str(state["thread_id"]),
            }
        }

    async def invoke(
        self,
        state: GraphState,
    ) -> GraphState:

        return await self.graph.ainvoke(
            state,
            config=self._config(state),
        )

    async def stream(
        self,
        state: GraphState,
    ):
        """
        Streams token-level chunks pushed by LLMNode via
        get_stream_writer() (see packages/graph/nodes/llm.py). Requires
        stream_mode="custom" — the default "updates" mode only yields
        one event per whole node completion, not per token.
        """

        async for event in self.graph.astream(
            state,
            config=self._config(state),
            stream_mode="custom",
        ):
            yield event