# Chat service
from __future__ import annotations
from collections.abc import AsyncIterator, Iterator
from langchain_core.messages import AIMessage
from packages.infrastructure.ai import LLMManager
from .request import ChatRequest
from .response import ChatResponse


class ChatService:
    """
    Stateless service responsible for communicating with the LLM.
    """

    def __init__(self, llm: LLMManager | None = None):
        self._llm = llm or LLMManager()

    def _model(self, request: ChatRequest):
        if request.tools:
            return self._llm.bind_tools(request.tools)
        return self._llm

    def chat_sync(self, request: ChatRequest) -> ChatResponse:
        """
        Execute a synchronous chat request.
        """

        response: AIMessage = self._model(request).invoke(
            request.messages
        )

        return ChatResponse(
            message=response,
            usage=response.usage_metadata or {},
            provider=str(self._llm.config.provider),
            model=self._llm.config.model,
        )

    async def chat(
        self,
        request: ChatRequest,
    ) -> ChatResponse:
        """
        Execute an asynchronous chat request.
        """

        response: AIMessage = await self._model(request).ainvoke(
            request.messages
        )

        return ChatResponse(
            message=response,
            usage=response.usage_metadata or {},
            provider=str(self._llm.config.provider),
            model=self._llm.config.model,
        )

    def stream(
        self,
        request: ChatRequest,
    ) -> Iterator:
        """
        Stream model output.
        """

        yield from self._llm.stream(
            request.messages
        )

    async def astream(
        self,
        request: ChatRequest,
    ) -> AsyncIterator:
        """
        Stream model output asynchronously.
        """

        async for chunk in self._model(request).astream(
            request.messages
        ):
            yield chunk

    def bind_tools(self, tools):
        """
        Bind tools to the underlying model.
        """

        return self._llm.bind_tools(tools)

    def with_structured_output(self, schema):
        """
        Bind a structured output schema.
        """

        return self._llm.with_structured_output(schema)