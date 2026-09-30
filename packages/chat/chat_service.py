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

    def _llm_for(self, request: ChatRequest) -> LLMManager:
        # request.llm_config is set when the conversation's agent has a
        # non-default ModelProfile (docs/BUGS.md item 15) — a fresh,
        # stateless provider built just for this one call, never mutating
        # the shared `self._llm` Singleton (which stays bound to the global
        # default and is what every other request still uses). Cheap: every
        # LLMFactory.create() call already constructs a stateless wrapper,
        # the same thing LLMManager.__init__ does internally.
        if request.llm_config is not None:
            return LLMManager(request.llm_config)
        return self._llm

    def _model(self, request: ChatRequest, llm: LLMManager):
        if request.tools:
            return llm.bind_tools(request.tools)
        return llm

    def chat_sync(self, request: ChatRequest) -> ChatResponse:
        """
        Execute a synchronous chat request.
        """

        self._breaker.check()
        llm = self._llm_for(request)

        try:
            response: AIMessage = self._model(request, llm).invoke(
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
            provider=str(llm.config.provider),
            model=llm.config.model,
        )

    async def chat(
        self,
        request: ChatRequest,
    ) -> ChatResponse:
        """
        Execute an asynchronous chat request.
        """

        self._breaker.check()
        llm = self._llm_for(request)

        try:
            response: AIMessage = await self._model(request, llm).ainvoke(
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
            provider=str(llm.config.provider),
            model=llm.config.model,
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
            yield from self._model(request, self._llm_for(request)).stream(
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
            async for chunk in self._model(request, self._llm_for(request)).astream(
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