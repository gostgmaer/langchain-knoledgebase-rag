"""
packages/graph/nodes/tool.py
"""

from __future__ import annotations

from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt

from packages.shared.logging import get_logger
from packages.tools.manager import ToolManager

logger = get_logger(__name__)


class GraphToolNode:
    """
    Executes LLM tool calls.

    Gates every tool call behind a human approval — LangGraph (Phase
    5)'s "Interrupt"/"Resume" gap, and the mechanism Phase 11 (Human in
    the Loop)'s approval workflow is built on. `interrupt()` pauses the
    graph here and surfaces the pending tool calls to the caller (see
    packages/application/services/chat_service.py's `_finalize_or_pause`);
    resuming later with `Command(resume={"approved": bool})` — even in
    a completely separate HTTP request, since the Postgres-backed
    checkpointer already persists state at the interrupt point — either
    lets this method proceed to the real `ToolNode`, or short-circuits
    with a synthetic rejection `ToolMessage` per call so the graph can
    still route to `llm` cleanly instead of dead-ending.

    All tools today (calculator, weather, web search, news) are
    read-only — this is deliberately a generic, always-on gate that
    demonstrates the mechanism correctly, not a response to any of them
    being individually dangerous.
    """

    def __init__(
        self,
        tool_manager: ToolManager,
    ) -> None:
        self._tool_node = ToolNode(
            tools=tool_manager.list(),
        )

    async def __call__(
        self,
        state,
    ):
        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", None) or []

        if not tool_calls:
            return await self._tool_node.ainvoke(state)

        decision = interrupt(
            {
                "type": "tool_approval",
                "tool_calls": [
                    {
                        "id": call.get("id"),
                        "name": call.get("name"),
                        "args": call.get("args"),
                    }
                    for call in tool_calls
                ],
            }
        )

        if not isinstance(decision, dict) or not decision.get("approved"):
            logger.info(
                "Tool calls rejected",
                tool_call_ids=[call.get("id") for call in tool_calls],
            )
            return {
                "messages": [
                    ToolMessage(
                        content="Tool call rejected by user.",
                        tool_call_id=call.get("id"),
                        status="error",
                    )
                    for call in tool_calls
                ]
            }

        for call in tool_calls:
            logger.info("Tool called", tool=call.get("name"), tool_call_id=call.get("id"))

        result = await self._tool_node.ainvoke(state)

        for message in result.get("messages", []):
            logger.info(
                "Tool call finished",
                tool_call_id=getattr(message, "tool_call_id", None),
                status=getattr(message, "status", None),
            )

        return result