from __future__ import annotations

from typing import Any
from uuid import UUID

from langgraph.types import Command

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

    async def resume(
        self,
        thread_id: UUID,
        resume_value: Any,
    ) -> GraphState:
        """
        Resumes a graph run previously paused by `interrupt()` (see
        packages/graph/nodes/tool.py's tool-approval gate) — no fresh
        input state needed, since the Postgres-backed checkpointer
        already holds everything up to the interrupt point under this
        thread_id, even across a completely separate HTTP request.
        """

        config = {"configurable": {"thread_id": str(thread_id)}}

        return await self.graph.ainvoke(
            Command(resume=resume_value),
            config=config,
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

        If the tool-approval gate (packages/graph/nodes/tool.py) pauses
        the graph mid-stream, `stream_mode="custom"` surfaces nothing —
        interrupt() doesn't push to the stream writer — so the loop
        below would otherwise end silently with zero tokens and no
        indication anything is pending. Checking `aget_state()` after
        the loop and yielding one explicit "interrupt" event turns that
        into a real, detectable signal instead of a silently dropped
        response.
        """

        config = self._config(state)

        async for event in self.graph.astream(
            state,
            config=config,
            stream_mode="custom",
        ):
            yield event

        snapshot = await self.graph.aget_state(config)

        if snapshot.next:
            for task in snapshot.tasks:
                if task.interrupts:
                    yield {"type": "interrupt", "value": task.interrupts[0].value}
                    return