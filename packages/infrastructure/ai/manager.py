from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable

from packages.infrastructure.ai.base import BaseLLMProvider
from packages.infrastructure.ai.config import (
    LLMConfig,
    get_default_llm_config,
)
from packages.infrastructure.ai.providers.factory import LLMFactory
from packages.infrastructure.ai.types import ChatModel


class LLMManager:
    """
    Production wrapper around language model providers.
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        self._config = config or get_default_llm_config()
        self._provider = LLMFactory.create(self._config)

    @property
    def provider(self) -> BaseLLMProvider:
        return self._provider

    @property
    def model(self) -> ChatModel:
        return self._provider.model

    @property
    def config(self) -> LLMConfig:
        return self._config

    ###########################################################################
    # Invoke
    ###########################################################################
    def configure(
        self,
        config: LLMConfig,
    ) -> None:
        """
        Reconfigure the manager with a different provider/model.
        """

        self._config = config
        self._provider = LLMFactory.create(config)

    def invoke(
        self,
        messages: list[BaseMessage],
        **kwargs: Any,
    ) -> AIMessage:
        return self._provider.invoke(messages, **kwargs)

    async def ainvoke(
        self,
        messages: list[BaseMessage],
        **kwargs: Any,
    ) -> AIMessage:
        return await self._provider.ainvoke(messages, **kwargs)

    ###########################################################################
    # Streaming
    ###########################################################################

    def stream(
        self,
        messages: list[BaseMessage],
        **kwargs: Any,
    ) -> Iterator[AIMessage]:
        yield from self._provider.stream(messages, **kwargs)

    async def astream(
        self,
        messages: list[BaseMessage],
        **kwargs: Any,
    ) -> AsyncIterator[AIMessage]:
        async for chunk in self._provider.astream(messages, **kwargs):
            yield chunk

    ###########################################################################
    # Tool Calling
    ###########################################################################

    def bind_tools(
        self,
        tools: list[Any],
        **kwargs: Any,
    ) -> Runnable:
        return self._provider.bind_tools(tools, **kwargs)

    ###########################################################################
    # Structured Output
    ###########################################################################

    def with_structured_output(
        self,
        schema: Any,
        **kwargs: Any,
    ) -> Runnable:
        return self._provider.with_structured_output(schema, **kwargs)
