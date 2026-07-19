from __future__ import annotations

from langchain_core.messages import AIMessage, BaseMessage

from packages.application.services.history_services import HistoryService
from packages.domain.models.conversation import Conversation
from packages.domain.models.message import Message
from packages.infrastructure.ai.manager import LLMManager
from packages.infrastructure.ai.prompts.builder import PromptBuilder
from packages.infrastructure.ai.prompts.context import PromptContext
from packages.infrastructure.ai.runtime.models import RuntimeResponse


class RuntimeService:
    """
    Executes the AI runtime.

    Responsibilities
    ----------------
    - Build the prompt
    - Invoke the language model
    - Normalize the response
    """

    def __init__(
        self,
        llm: LLMManager,
        prompt_builder: PromptBuilder,
        history_service: HistoryService,
    ) -> None:
        self._llm = llm
        self._prompt_builder = prompt_builder
        self._history_service = history_service

    async def run(
        self,
        conversation: Conversation,
        user_message: Message,
    ) -> RuntimeResponse:
        """
        Execute the AI runtime.
        """

        prompt = self._build_prompt(
            conversation,
            user_message,
        )

        response = await self._invoke_model(
            prompt,
        )

        return self._build_response(
            response,
        )

    ###########################################################################
    # Prompt
    ###########################################################################

    def _build_prompt(
        self,
        conversation: Conversation,
        user_message: Message,
    ) -> list[BaseMessage]:

        context = PromptContext(
            conversation=conversation,
            user_message=user_message,
        )

        return self._prompt_builder.build(
            context,
        )

    ###########################################################################
    # Model Invocation
    ###########################################################################

    async def _invoke_model(
        self,
        messages: list[BaseMessage],
    ) -> AIMessage:

        response = await self._llm.ainvoke(
            messages,
        )

        if not isinstance(response, AIMessage):
            raise TypeError(
                "LLMManager must return an AIMessage."
            )

        return response

    ###########################################################################
    # Response
    ###########################################################################

    def _build_response(
        self,
        response: AIMessage,
    ) -> RuntimeResponse:

        metadata = self._extract_metadata(
            response,
        )

        usage = metadata.get(
            "token_usage",
            {},
        )

        return RuntimeResponse(
            provider=self._llm.config.provider,
            message=response,
            model=metadata.get(
                "model_name",
            ),
            prompt_tokens=usage.get(
                "prompt_tokens",
                0,
            ),
            completion_tokens=usage.get(
                "completion_tokens",
                0,
            ),
            total_tokens=usage.get(
                "total_tokens",
                0,
            ),
            finish_reason=metadata.get(
                "finish_reason",
            ),
            metadata=metadata,
        )

    ###########################################################################
    # Metadata
    ###########################################################################

    def _extract_metadata(
        self,
        response: AIMessage,
    ) -> dict:

        return response.response_metadata or {}