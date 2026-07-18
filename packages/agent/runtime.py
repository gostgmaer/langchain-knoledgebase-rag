from __future__ import annotations

from langchain_core.messages import AIMessage

from packages.agent.prompt import PromptBuilder
from packages.agent.response import AgentResponse, AgentUsage
from packages.graph.state import GraphState
from packages.infrastructure.ai.manager import LLMManager


class AgentRuntime:

    def __init__(
        self,
        llm: LLMManager,
        prompt_builder: PromptBuilder,
    ) -> None:
        self.llm = llm
        self.prompt_builder = prompt_builder

    async def run(
        self,
        state: GraphState,
    ) -> AgentResponse:

        messages = self.prompt_builder.build(state)

        response = await self.llm.ainvoke(messages)

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