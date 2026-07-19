from __future__ import annotations

from abc import ABC
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from packages.infrastructure.ai.base import BaseLLMProvider
from packages.infrastructure.ai.config import LLMConfig


class BaseProvider(BaseLLMProvider, ABC):
    """
    Base implementation shared by all LLM providers.
    Concrete providers are only responsible for creating
    the underlying LangChain chat model.
    """

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._model = self._create_model()

    @property
    def config(self) -> LLMConfig:
        return self._config

    @property
    def model(self) -> BaseChatModel:
        return self._model

    def invoke(self, *args: Any, **kwargs: Any):
        return self._model.invoke(*args, **kwargs)

    async def ainvoke(self, *args: Any, **kwargs: Any):
        return await self._model.ainvoke(*args, **kwargs)

    def stream(self, *args: Any, **kwargs: Any):
        return self._model.stream(*args, **kwargs)

    async def astream(self, *args: Any, **kwargs: Any):
        async for chunk in self._model.astream(*args, **kwargs):
            yield chunk

    def bind_tools(self, tools: list[Any]):
        return self._model.bind_tools(tools)

    def with_structured_output(self, schema: Any):
        return self._model.with_structured_output(schema)

    def _create_model(self) -> BaseChatModel:
        """
        Must be implemented by concrete providers.
        """
        raise NotImplementedError