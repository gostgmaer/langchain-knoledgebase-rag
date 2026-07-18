from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable

from .registry import LLMRegistry
from .types import ChatModel


class LLMManager:
    """
    Production wrapper around LangChain chat models.

    Responsibilities
    ----------------
    • Initialize the configured model
    • Provide a stable interface for the application
    • Hide provider-specific implementations
    • Support tools
    • Support structured output
    • Support streaming
    """

    def __init__(self) -> None:
        self._model: ChatModel = LLMRegistry.create()

    @property
    def model(self) -> ChatModel:
        return self._model

    ###########################################################################
    # Invoke
    ###########################################################################

    def invoke(
        self,
        messages: list[BaseMessage],
        **kwargs: Any,
    ) -> AIMessage:

        return self._model.invoke(
            messages,
            **kwargs,
        )

    async def ainvoke(
        self,
        messages: list[BaseMessage],
        **kwargs: Any,
    ) -> AIMessage:

        return await self._model.ainvoke(
            messages,
            **kwargs,
        )

    ###########################################################################
    # Streaming
    ###########################################################################

    def stream(
        self,
        messages: list[BaseMessage],
        **kwargs: Any,
    ) -> Iterator[AIMessage]:

        yield from self._model.stream(
            messages,
            **kwargs,
        )

    async def astream(
        self,
        messages: list[BaseMessage],
        **kwargs: Any,
    ) -> AsyncIterator[AIMessage]:

        async for chunk in self._model.astream(
            messages,
            **kwargs,
        ):
            yield chunk

    ###########################################################################
    # Tool Calling
    ###########################################################################

    def bind_tools(
        self,
        tools: list[Any],
        **kwargs: Any,
    ) -> Runnable:

        return self._model.bind_tools(
            tools,
            **kwargs,
        )

    ###########################################################################
    # Structured Output
    ###########################################################################

    def with_structured_output(
        self,
        schema: Any,
        **kwargs: Any,
    ) -> Runnable:

        return self._model.with_structured_output(
            schema,
            **kwargs,
        )
