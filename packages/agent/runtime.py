from __future__ import annotations

from typing import TYPE_CHECKING

from packages.agent.prompt import PromptBuilder
from packages.agent.response import AgentResponse
from packages.agent.response import AgentUsage
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
        self._llm = llm
        self._prompt_builder = prompt_builder
        self._tools = tools

    async def run(
        self,
        state: GraphState,
    ) -> AgentResponse:
        """
        Execute one LLM step.
        """

        #
        # Build prompt from the complete graph state.
        #
        messages = self._prompt_builder.build(
            state,
        )

        #
        # Bind available tools.
        #
        model = self._llm.model

        tools = self._tools.list()

        if tools:
            model = model.bind_tools(
                tools,
            )

        #
        # Invoke model.
        #
        response = await model.ainvoke(
            messages,
        )

        #
        # Usage
        #
        usage = AgentUsage()

        if getattr(response, "usage_metadata", None):
            metadata = response.usage_metadata

            usage = AgentUsage(
                input_tokens=metadata.get("input_tokens", 0),
                output_tokens=metadata.get("output_tokens", 0),
                total_tokens=metadata.get("total_tokens", 0),
            )

        #
        # Return normalized response.
        #
        return AgentResponse(
            message=response,
            model=str(state.get("model_profile_id", "")),
            usage=usage,
            tool_calls=getattr(response, "tool_calls", []),
            finish_reason=response.response_metadata.get(
                "finish_reason",
            ),
            metadata=response.response_metadata,
        )