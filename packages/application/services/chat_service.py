import time
from collections.abc import AsyncIterator
from uuid import UUID

from packages.application.dto.chat import (
    ChatRequest,
    ChatResponse,
    CitationDTO,
    PendingApprovalDTO,
    PendingToolCallDTO,
)
from packages.application.dto.conversation import (
    ConversationResponse,
    CreateConversationRequest,
)
from packages.application.services.conversation_service import (
    ConversationService,
)
from packages.application.services.message_service import (
    MessageService,
)
from packages.conversation.context import ConversationContextBuilder
from packages.domain.models.message import Message
from packages.graph.manager import GraphManager
from packages.infrastructure.repositories.unit_of_work import (
    UnitOfWork,
)


class ChatService:

    def __init__(
        self,
        uow: UnitOfWork,
        conversation_service: ConversationService,
        message_service: MessageService,
        graph: GraphManager,
        context: ConversationContextBuilder,
    ) -> None:

        self._uow = uow
        self._conversation_service = conversation_service
        self._message_service = message_service
        self._graph = graph
        self._context = context

    async def chat(
        self,
        request: ChatRequest,
    ) -> ChatResponse:
        try:
            conversation = await self._get_conversation(request)

            user_message = await self._save_user_message(
                conversation,
                request,
            )

            state = await self._build_state(conversation, stream=False)

            started = time.perf_counter()
            result = await self._graph.invoke(state)
            latency_ms = int((time.perf_counter() - started) * 1000)

            return await self._finalize_or_pause(conversation, user_message, result, latency_ms)

        except Exception:
            await self._uow.rollback()
            raise

    async def resume(
        self,
        conversation_id: UUID,
        approved: bool,
    ) -> ChatResponse:
        """
        Resumes a conversation previously paused by the tool-approval
        gate (packages/graph/nodes/tool.py) — Phase 11 (Human in the
        Loop)'s approval workflow. No new user message is involved;
        this responds to a pending tool call from an earlier turn, not
        a fresh chat message. Deliberately non-streaming only, same as
        citations — the streaming path is a documented gap, not a
        silent omission.
        """

        try:
            conversation = await self._conversation_service.get(conversation_id)

            started = time.perf_counter()
            result = await self._graph.resume(
                conversation_id,
                {"approved": approved},
            )
            latency_ms = int((time.perf_counter() - started) * 1000)

            return await self._finalize_or_pause(conversation, None, result, latency_ms)

        except Exception:
            await self._uow.rollback()
            raise

    async def _finalize_or_pause(
        self,
        conversation: ConversationResponse,
        user_message: Message | None,
        result: dict,
        latency_ms: int,
    ) -> ChatResponse:
        """
        Shared tail for both chat() and resume(): a graph run either
        completed (a real assistant message to persist) or paused again
        on another tool-approval gate (nothing to persist yet — the
        checkpointer already holds everything, waiting for the next
        resume() call).
        """

        interrupts = result.get("__interrupt__")

        if interrupts:
            pending = interrupts[0].value
            return ChatResponse(
                conversation_id=conversation.id,
                user_message_id=user_message.id if user_message else None,
                pending_approval=PendingApprovalDTO(
                    tool_calls=[
                        PendingToolCallDTO(**call)
                        for call in pending.get("tool_calls", [])
                    ]
                ),
            )

        citations = [
            CitationDTO(
                document_id=citation.document_id,
                chunk_id=citation.chunk_id,
                chunk_index=citation.chunk_index,
                score=citation.score,
            )
            for citation in result.get("citations") or []
        ]

        final_message = result["messages"][-1]
        raw_response = {
            "response_metadata": getattr(final_message, "response_metadata", None) or {},
            "additional_kwargs": getattr(final_message, "additional_kwargs", None) or {},
            "usage_metadata": getattr(final_message, "usage_metadata", None) or {},
        }

        # result["usage"] is the graph-level accumulated total across
        # however many LLM calls this turn made (see merge_usage() in
        # packages/graph/state.py) — not final_message.usage_metadata,
        # which only ever reflects the *last* call and would undercount
        # a tool-calling turn's real token usage.
        usage = result.get("usage") or {}

        assistant_message = await self._save_assistant_message(
            conversation,
            final_message.content,
            raw_response,
            usage=usage,
            latency_ms=latency_ms,
        )

        await self._update_conversation(conversation)

        await self._uow.commit()

        return ChatResponse(
            conversation_id=conversation.id,
            user_message_id=user_message.id if user_message else None,
            assistant_message_id=assistant_message.id,
            response=final_message.content,
            citations=citations,
        )

    async def stream(
        self,
        request: ChatRequest,
    ) -> AsyncIterator[dict]:
        """
        Same flow as chat(), but streams the assistant's response
        token-by-token as it's generated instead of waiting for the
        full response. The full text is still persisted as one
        assistant message once streaming completes.

        Yields `{"type": "token", "content": str}` for real content, or
        a single terminal `{"type": "interrupt", "tool_calls": [...]}`
        if the tool-approval gate paused the graph mid-stream — the
        caller (packages/api/routers/chat.py's `_sse_events`) must
        check for that type and skip persistence/the "done" event, the
        same way it already has to for a normal completion.
        """
        try:
            conversation = await self._get_conversation(request)

            user_message = await self._save_user_message(
                conversation,
                request,
            )

            chunks: list[str] = []
            raw_response: dict = {}
            pending_approval: dict = {}
            usage: dict = {}

            started = time.perf_counter()

            async for token in self._stream_runtime(
                conversation, user_message, raw_response, pending_approval, usage
            ):
                chunks.append(token)
                yield {"type": "token", "content": token}

            latency_ms = int((time.perf_counter() - started) * 1000)

            if pending_approval:
                yield {
                    "type": "interrupt",
                    "tool_calls": pending_approval.get("tool_calls", []),
                }
                return

            assistant_response = "".join(chunks)

            await self._save_assistant_message(
                conversation,
                assistant_response,
                raw_response,
                usage=usage,
                latency_ms=latency_ms,
            )

            await self._update_conversation(conversation)

            await self._uow.commit()

        except Exception:
            await self._uow.rollback()
            raise

    async def _get_conversation(
        self,
        request: ChatRequest,
    ) -> ConversationResponse:
        return await self._conversation_service.get_or_create(
            CreateConversationRequest(
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                agent_id=request.agent_id,
                session_id=request.session_id,
            )
        )

    async def _save_user_message(
        self,
        conversation: ConversationResponse,
        request: ChatRequest,
    ) -> Message:
        return await self._message_service.create_user_message(
            conversation_id=conversation.id,
            content=request.message,
        )

    async def _build_state(
        self,
        conversation: ConversationResponse,
        stream: bool,
    ) -> dict:

        agent = await self._uow.agents.get(conversation.agent_id)

        history = await self._context.build(
            conversation_id=conversation.id,
            system_prompt=agent.system_prompt,
        )

        return {
            "messages": history,
            "conversation_id": conversation.id,
            "thread_id": conversation.id,
            "tenant_id": conversation.tenant_id,
            "user_id": conversation.user_id,
            "model_profile_id": agent.model_profile_id,
            "system_prompt": agent.system_prompt,
            "temperature": float(agent.temperature),
            "max_tokens": agent.max_tokens,
            "retrieval_enabled": True,
            "tools_enabled": True,
            "stream": stream,
            "search_results": [],
            "context": None,
            "citations": [],
            "tool_calls": [],
            "tool_results": [],
            "memories": [],
            # None (not {}) is a deliberate reset signal merge_usage()
            # special-cases — see its own docstring in
            # packages/graph/state.py for why {} would be a no-op
            # merge against the prior turn's already-checkpointed
            # value instead of actually resetting it.
            "usage": None,
        }

    async def _stream_runtime(
        self,
        conversation: ConversationResponse,
        message: Message,
        raw_response: dict,
        pending_approval: dict,
        usage: dict,
    ) -> AsyncIterator[str]:
        """
        Runs the real LangGraph pipeline (planner, retrieval, tools,
        memory extraction) for this conversation, yielding each token
        chunk pushed by LLMNode's stream writer as it arrives, instead
        of waiting for the full graph run to finish. `raw_response` is
        mutated in place with the one "metadata" event LLMNode emits
        after the token loop ends — stream_mode="custom" never
        surfaces the final graph state directly, so this is the only
        way the raw provider response reaches the caller once
        streaming completes. `pending_approval` is mutated the same
        way if the tool-approval gate (packages/graph/nodes/tool.py)
        paused the graph instead — see GraphManager.stream()'s own
        "interrupt" event. `usage` is mutated the same way from the
        "usage" event (Token Usage/Cost Tracking) — same reasoning,
        it's otherwise unreachable once the stream ends.
        """

        state = await self._build_state(conversation, stream=True)

        async for event in self._graph.stream(state):
            if not isinstance(event, dict):
                continue
            if event.get("type") == "token":
                yield event["content"]
            elif event.get("type") == "metadata":
                raw_response["response_metadata"] = event.get("response_metadata", {})
                raw_response["additional_kwargs"] = event.get("additional_kwargs", {})
            elif event.get("type") == "usage":
                usage.update(event.get("usage") or {})
            elif event.get("type") == "interrupt":
                pending_approval["tool_calls"] = event.get("value", {}).get(
                    "tool_calls", []
                )

    async def _save_assistant_message(
        self,
        conversation: ConversationResponse,
        response: str,
        raw_response: dict | None = None,
        usage: dict | None = None,
        latency_ms: int | None = None,
    ) -> Message:
        agent = await self._uow.agents.get(conversation.agent_id)

        return await self._message_service.create_assistant_message(
            conversation_id=conversation.id,
            content=response,
            provider=agent.llm_provider if agent else None,
            model=agent.llm_model if agent else None,
            raw_response=raw_response,
            usage=usage,
            latency_ms=latency_ms,
        )

    async def _update_conversation(
        self,
        conversation: ConversationResponse,
    ) -> None:
        await self._conversation_service.touch(
            conversation.id,
        )
