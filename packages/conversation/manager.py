from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from langchain_core.messages import HumanMessage

from packages.conversation.context import (
    ConversationContextBuilder,
)
from packages.conversation.models import (
    ChatRequest,
    ChatResponse,
)
from packages.conversation.service import (
    ConversationService,
)
from packages.domain.models.message import Message
from packages.domain.enums.message_role import MessageRole
from packages.graph.state import GraphState

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from packages.graph.manager import GraphManager


class ConversationManager:
    """
    High-level conversation orchestrator.

    Responsible for:

    - validating conversation
    - persisting messages
    - building graph state
    - invoking LangGraph
    - saving assistant response
    """

    def __init__(
        self,
        service: ConversationService,
        context: ConversationContextBuilder,
        graph: GraphManager,
    ) -> None:

        self.service = service
        self.context = context
        self.graph = graph

    async def chat(
        self,
        request: ChatRequest,
    ) -> ChatResponse:

        #
        # Ensure conversation exists
        #

        conversation = await self.service.get(
            request.conversation_id,
        )

        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )

        #
        # Save user message
        #

        print(f"\n[ConversationManager] RECEIVED USER MESSAGE: {request.message}\n")

        await self.service.add_message(
            Message(
                conversation_id=request.conversation_id,
                role=MessageRole.USER,
                content=request.message,
            )
        )

        #
        # Build history
        #

        # Build history
        history = await self.context.build(
            conversation_id=request.conversation_id,
            system_prompt=request.system_prompt,
        )

        #
        # Build GraphState
        #

        state = self._build_graph_state(
            request,
            conversation,
            history,
        )

        #
        # Execute graph
        #

        result = await self.graph.invoke(
            state,
        )

        assistant = result["messages"][-1]

        assistant_content = assistant.content
        if isinstance(assistant_content, list):
            text_parts = []
            for part in assistant_content:
                if isinstance(part, str):
                    text_parts.append(part)
                elif isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
            assistant_content = "\n".join(text_parts)

        #
        # Persist assistant message
        #

        await self.service.add_message(
            Message(
                conversation_id=request.conversation_id,
                role=MessageRole.ASSISTANT,
                content=assistant_content,
            )
        )

        return ChatResponse(
            conversation_id=request.conversation_id,
            response=assistant_content,
            model="default",
        )

    def _build_graph_state(
        self,
        request: ChatRequest,
        conversation,
        history,
    ) -> GraphState:

        return {
            #
            # Conversation
            #
            "messages": history,
            "conversation_id": request.conversation_id,
            "thread_id": request.conversation_id,
            "tenant_id": conversation.tenant_id,
            "user_id": request.user_id,
            #
            # AI
            #
            "model_profile_id": conversation.agent.model_profile_id,
            "system_prompt": request.system_prompt,
            "temperature": conversation.agent.temperature,
            "max_tokens": conversation.agent.max_tokens,
            #
            # Runtime
            #
            "retrieval_enabled": True,
            "tools_enabled": True,
            "stream": False,
            #
            # RAG
            #
            "search_results": [],
            "context": None,
            "citations": [],
            #
            # Tools
            #
            "tool_calls": [],
            "tool_results": [],
            #
            # Memory
            #
            "summary": "",
            #
            # Execution
            #
            "next_node": "",
            "metadata": {},
            "usage": {},
            #
            # Errors
            #
            "retry_count": 0,
            "error": None,
        }
