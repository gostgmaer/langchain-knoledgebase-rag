from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable


class BaseLLMProvider(ABC):
    """
    Abstract interface for all chat model providers.

    Every provider (Google, OpenAI, Anthropic, Groq, Ollama, etc.)
    must implement this interface so the rest of the application
    remains provider-agnostic.
    """

    @property
    @abstractmethod
    def model(self) -> BaseChatModel:
        """Return the underlying LangChain chat model."""
        raise NotImplementedError

    @abstractmethod
    def invoke(
        self,
        messages: list[BaseMessage],
        **kwargs: Any,
    ) -> AIMessage:
        """Synchronously invoke the model."""
        raise NotImplementedError

    @abstractmethod
    async def ainvoke(
        self,
        messages: list[BaseMessage],
        **kwargs: Any,
    ) -> AIMessage:
        """Asynchronously invoke the model."""
        raise NotImplementedError

    @abstractmethod
    def stream(
        self,
        messages: list[BaseMessage],
        **kwargs: Any,
    ) -> Iterator[AIMessage]:
        """Synchronously stream model responses."""
        raise NotImplementedError

    @abstractmethod
    async def astream(
        self,
        messages: list[BaseMessage],
        **kwargs: Any,
    ) -> AsyncIterator[AIMessage]:
        """Asynchronously stream model responses."""
        raise NotImplementedError

    @abstractmethod
    def bind_tools(
        self,
        tools: list[Any],
    ) -> Runnable:
        """Return a runnable with tools bound."""
        raise NotImplementedError

    @abstractmethod
    def with_structured_output(
        self,
        schema: type | dict[str, Any],
    ) -> Runnable:
        """Return a runnable configured for structured output."""
        raise NotImplementedError