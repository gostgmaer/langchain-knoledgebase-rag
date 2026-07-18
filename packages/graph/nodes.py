# Graph nodes
from __future__ import annotations

from dataclasses import dataclass

from packages.infrastructure.ai.manager import LLMManager
from packages.memory.manager import MemoryManager
from packages.rag.manager import RAGManager
from packages.tools.manager import ToolManager
from packages.graph.state import GraphState


@dataclass(slots=True)
class NodeContext:
    ai: LLMManager
    rag: RAGManager
    tools: ToolManager
    memory: MemoryManager


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

        query = state["messages"][-1].content

        documents = await self.context.rag.retrieve(
            query=query,
        )

        return {
            "documents": documents,
        }

    async def llm(
        self,
        state: GraphState,
    ) -> GraphState:

        messages = state["messages"]

        if state.get("documents"):

            context = "\n\n".join(
                doc.page_content
                for doc in state["documents"]
            )

            messages = [
                *messages,
            ]

            messages.insert(
                0,
                {
                    "role": "system",
                    "content": context,
                },
            )

        response = await self.context.ai.chat(
            messages,
        )

        return {
            "messages": [response],
        }

    async def tool(
        self,
        state: GraphState,
    ) -> GraphState:

        result = await self.context.tools.execute(
            state["messages"],
        )

        return {
            "messages": result,
        }

    async def summarize(
        self,
        state: GraphState,
    ) -> GraphState:

        summary = await self.context.memory.summarize(
            state["messages"],
        )

        return {
            "summary": summary,
        }