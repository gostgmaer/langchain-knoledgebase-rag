from __future__ import annotations
from typing import TYPE_CHECKING
from packages.agent.prompt import PromptBuilder
from packages.agent.response import AgentResponse, AgentUsage
from packages.infrastructure.ai.manager import LLMManager
from packages.tools.manager import ToolManager

if TYPE_CHECKING:
    from packages.graph.state import GraphState


class AgentRuntime:

    def __init__(
        self,
        llm: LLMManager,
        prompt_builder: PromptBuilder,
        tools: ToolManager,
    ) -> None:
        self.llm = llm
        self.prompt_builder = prompt_builder
        self.tools = tools

    async def run(
        self,
        state: GraphState,
    ) -> AgentResponse:

        messages = self.prompt_builder.build(state)
        tools = self.tools.list()
        model = self.llm.model

        if tools:
            model = model.bind_tools(tools)
        response = await model.ainvoke(messages)

        usage = AgentUsage()

        if getattr(response, "usage_metadata", None):
            metadata = response.usage_metadata

            usage = AgentUsage(
                input_tokens=metadata.get("input_tokens", 0),
                output_tokens=metadata.get("output_tokens", 0),
                total_tokens=metadata.get("total_tokens", 0),
            )

        return AgentResponse(
            message=response,
            model=state.get("model", ""),
            usage=usage,
            tool_calls=getattr(response, "tool_calls", []),
            finish_reason=response.response_metadata.get(
                "finish_reason",
            ),
            metadata=response.response_metadata,
        )
