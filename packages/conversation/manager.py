from __future__ import annotations

from uuid import UUID

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
            raise ValueError("Conversation not found.")

        #
        # Save user message
        #

        await self.service.add_message(
            conversation_id=request.conversation_id,
            role="user",
            content=request.message,
        )

        #
        # Build history
        #

        history = await self.context.build(
            conversation_id=request.conversation_id,
            system_prompt=request.system_prompt,
        )

        #
        # Append latest user message
        #

        history.append(
            HumanMessage(
                content=request.message,
            )
        )

        #
        # Build GraphState
        #

        state: GraphState = {
            "messages": history,
            "conversation_id": str(request.conversation_id),
            "user_id": str(request.user_id),
            "thread_id": str(request.conversation_id),
        }

        #
        # Execute graph
        #

        result = await self.graph.invoke(
            state,
        )

        assistant = result["messages"][-1]

        #
        # Persist assistant message
        #

        await self.service.add_message(
            conversation_id=request.conversation_id,
            role="assistant",
            content=assistant.content,
        )

        return ChatResponse(
            conversation_id=request.conversation_id,
            message=assistant.content,
        )
