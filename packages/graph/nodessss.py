from __future__ import annotations

from dataclasses import dataclass


from packages.agent.runtime import AgentRuntime
from packages.graph.nodes.planner import GraphPlanner
from packages.graph.state import GraphState
from packages.memory.manager import MemoryManager
from packages.rag.manager import RAGManager
from packages.rag.schemas import RAGRequest
from packages.tools.manager import ToolManager
from langchain_core.messages import ToolMessage


@dataclass(slots=True)
class NodeContext:
    runtime: AgentRuntime
    rag: RAGManager
    tools: ToolManager
    memory: MemoryManager
    planner: GraphPlanner


class GraphNodes:

    def __init__(
        self,
        context: NodeContext,
    ) -> None:
        self.context = context

    async def retrieve(
    self,
    state: GraphState,
) -> GraphState:

        request = RAGRequest(
        tenant_id=state["tenant_id"],
        model_profile_id=state["model_profile_id"],
        query=state["messages"][-1].content,
        conversation_id=state.get("conversation_id"),
        system_prompt=state.get("system_prompt"),
        metadata=state.get("metadata", {}),
    )

        search_results = await self.context.rag.retrieve(
        request,
    )

        context = self.context.rag.build_context(
        search_results,
    )

        citations = self.context.rag.build_citations(
        search_results,
    )

        return {
        "search_results": search_results,
        "context": context,
        "citations": citations,
    }

    async def tool(
        self,
        state: GraphState,
    ) -> GraphState:

        ai_message = state["messages"][-1]

       

        tool_messages = []

        for tool_call in ai_message.tool_calls:
            result = await self.context.tools.execute(
                tool_call["name"],
                **tool_call["args"],
            )

            tool_messages.append(
                ToolMessage(
                    content=str(result),
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"],
                )
            )

        return {
            "messages": tool_messages,
        }

    async def llm(
        self,
        state: GraphState,
    ) -> GraphState:

        response = await self.context.runtime.run(state)

        return {
            "messages": [response.message],
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }

    async def summarize(
        self,
        state: GraphState,
    ) -> GraphState:
        """
        Placeholder node.
        Conversation summarization will be implemented later.
        """
        return {}

    async def planner(
        self,
        state: GraphState,
    ):
        result = await self.context.planner.plan(state)

        return {
            "next_node": result.next_node,
        }
