# Chat service
from __future__ import annotations
from collections.abc import AsyncIterator, Iterator
from langchain_core.messages import AIMessage
from packages.infrastructure.ai import LLMManager
from packages.infrastructure.resilience.circuit_breaker import CircuitBreaker
from .request import ChatRequest
from .response import ChatResponse


class ChatService:
    """
    Stateless service responsible for communicating with the LLM.
    """

    def __init__(self, llm: LLMManager | None = None, breaker: CircuitBreaker | None = None):
        self._llm = llm or LLMManager()
        # Per-provider circuit breaker (one ChatService instance is a
        # Singleton bound to one active provider config for the whole
        # app) — a default is built here so direct instantiation outside
        # DI (tests, scripts) still works.
        self._breaker = breaker or CircuitBreaker(name="llm-provider")

    def _model(self, request: ChatRequest):
        if request.tools:
            return self._llm.bind_tools(request.tools)
        return self._llm

    def chat_sync(self, request: ChatRequest) -> ChatResponse:
        """
        Execute a synchronous chat request.
        """

        self._breaker.check()

        try:
            response: AIMessage = self._model(request).invoke(
                request.messages
            )
        except Exception:
            self._breaker.record_failure()
            raise
        else:
            self._breaker.record_success()

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

        self._breaker.check()

        try:
            response: AIMessage = await self._model(request).ainvoke(
                request.messages
            )
        except Exception:
            self._breaker.record_failure()
            raise
        else:
            self._breaker.record_success()

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

        self._breaker.check()

        try:
            yield from self._llm.stream(
                request.messages
            )
        except Exception:
            self._breaker.record_failure()
            raise
        else:
            self._breaker.record_success()

    async def astream(
        self,
        request: ChatRequest,
    ) -> AsyncIterator:
        """
        Stream model output asynchronously.
        """

        self._breaker.check()

        try:
            async for chunk in self._model(request).astream(
                request.messages
            ):
                yield chunk
        except Exception:
            self._breaker.record_failure()
            raise
        else:
            self._breaker.record_success()

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