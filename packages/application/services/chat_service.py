from collections.abc import AsyncIterator

from packages.application.dto.chat import ChatRequest, ChatResponse
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

from packages.domain.models.message import Message
from packages.graph.manager import GraphManager
from packages.conversation.context import ConversationContextBuilder
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

            assistant_response = await self._execute_runtime(
                conversation,
                user_message,
                stream=False,
            )

            assistant_message = await self._save_assistant_message(
                conversation,
                assistant_response,
            )

            await self._update_conversation(conversation)

            await self._uow.commit()

            return ChatResponse(
                conversation_id=conversation.id,
                user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                response=assistant_response,
            )

        except Exception:
            await self._uow.rollback()
            raise

    async def stream(
        self,
        request: ChatRequest,
    ) -> AsyncIterator[str]:
        """
        Same flow as chat(), but streams the assistant's response
        token-by-token as it's generated instead of waiting for the
        full response. The full text is still persisted as one
        assistant message once streaming completes.
        """
        try:
            conversation = await self._get_conversation(request)

            user_message = await self._save_user_message(
                conversation,
                request,
            )

            chunks: list[str] = []

            async for token in self._stream_runtime(conversation, user_message):
                chunks.append(token)
                yield token

            assistant_response = "".join(chunks)

            await self._save_assistant_message(
                conversation,
                assistant_response,
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
        }

    async def _execute_runtime(
        self,
        conversation: ConversationResponse,
        message: Message,
        stream: bool,
    ) -> str:
        """
        Runs the real LangGraph pipeline (planner, retrieval, tools,
        memory extraction) for this conversation and returns the
        assistant's final response text.
        """

        state = await self._build_state(conversation, stream)

        result = await self._graph.invoke(state)

        return result["messages"][-1].content

    async def _stream_runtime(
        self,
        conversation: ConversationResponse,
        message: Message,
    ) -> AsyncIterator[str]:
        """
        Same pipeline as _execute_runtime(), but yields each token
        chunk pushed by LLMNode's stream writer as it arrives, instead
        of waiting for the full graph run to finish.
        """

        state = await self._build_state(conversation, stream=True)

        async for event in self._graph.stream(state):
            if isinstance(event, dict) and event.get("type") == "token":
                yield event["content"]

    async def _save_assistant_message(
        self,
        conversation: ConversationResponse,
        response: str,
    ) -> Message:
        return await self._message_service.create_assistant_message(
            conversation_id=conversation.id,
            content=response,
        )

    async def _update_conversation(
        self,
        conversation: ConversationResponse,
    ) -> None:
        await self._conversation_service.touch(
            conversation.id,
        )
