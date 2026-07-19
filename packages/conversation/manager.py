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
from packages.graph.manager import GraphManager
from packages.graph.state import GraphState


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

        state: GraphState = {
            "messages": history,
            "conversation_id": str(request.conversation_id),
            "user_id": str(request.user_id),
            "thread_id": str(request.conversation_id),
            "documents": [],
            "tool_results": [],
            "next_node": None,
            "system_prompt": request.system_prompt,
        }

        #
        # Execute graph
        #

        result = await self.graph.invoke(
            state,
        )

        assistant = result["messages"][-1]

        assistant_content = assistant.content
        if isinstance(assistant_content, list):
            text_parts = [
                part.get("text", "")
                for part in assistant_content
                if isinstance(part, dict) and part.get("type") == "text"
            ]
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
