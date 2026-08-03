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

    async def has_pending_work(
        self,
        thread_id: UUID,
    ) -> bool:
        """
        True if this thread's checkpoint still has unexecuted nodes
        (`snapshot.next`) — False means the graph already reached END,
        so there's genuinely nothing to recover. Confirmed live this
        distinction matters: calling `recover()` unconditionally
        against an *already-completed* thread (the narrow crash-
        timing edge case documented on `recover()` below) doesn't
        error, it just re-runs the graph from its final checkpoint and
        returns that same final state again — which `ChatService.
        recover()` would otherwise persist as a second, duplicate
        assistant message.
        """

        config = {"configurable": {"thread_id": str(thread_id)}}
        snapshot = await self.graph.aget_state(config)

        return bool(snapshot.next)

    async def recover(
        self,
        thread_id: UUID,
    ) -> GraphState:
        """
        Continues a graph run left mid-flight by a crashed process
        (Durable Execution, docs/mvpRAG.md v2.0) — no fresh input and
        no `Command(resume=...)` payload, unlike `resume()` above:
        just letting LangGraph pick back up from wherever the last
        completed node's checkpoint under this thread_id left off.
        Called by ChatService.recover(), itself only ever called from
        `recover_stuck_conversations_job` (packages/worker/jobs.py),
        never an HTTP route directly. Callers should check
        `has_pending_work()` first — see its own docstring.
        """

        config = {"configurable": {"thread_id": str(thread_id)}}

        return await self.graph.ainvoke(
            None,
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