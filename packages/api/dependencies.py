# API dependencies
from __future__ import annotations

from dependency_injector.wiring import Provide, inject
from fastapi import Depends

from packages.infrastructure.ai.manager import LLMManager
from packages.conversation.manager import ConversationManager
from packages.graph.manager import GraphManager
from packages.infrastructure.container import ApplicationContainer
from packages.memory.manager import MemoryManager
from packages.rag.manager import RAGManager
from packages.tools.manager import ToolManager
from sqlalchemy.ext.asyncio import AsyncSession

# NOTE: dependency-injector's wiring does not see markers inside
# Annotated[...] metadata — keep Depends(Provide[...]) as a default value.


#
# Root Container
#


@inject
def get_container(
    container: ApplicationContainer = Depends(Provide[ApplicationContainer]),
) -> ApplicationContainer:
    return container

@inject
def get_db_session(
    session: AsyncSession = Depends(Provide[ApplicationContainer.database.session]),
) -> AsyncSession:
    return session


#
# AI
#


@inject
def get_ai_manager(
    manager: LLMManager = Depends(Provide[ApplicationContainer.ai.manager]),
) -> LLMManager:
    return manager


#
# Conversation
#


@inject
def get_conversation_manager(
    manager: ConversationManager = Depends(
        Provide[ApplicationContainer.conversation.manager]
    ),
) -> ConversationManager:
    return manager


#
# Graph
#


@inject
def get_graph_manager(
    manager: GraphManager = Depends(Provide[ApplicationContainer.graph.manager]),
) -> GraphManager:
    return manager


#
# Memory
#


@inject
def get_memory_manager(
    manager: MemoryManager = Depends(Provide[ApplicationContainer.memory.manager]),
) -> MemoryManager:
    return manager


#
# RAG
#


@inject
def get_rag_manager(
    manager: RAGManager = Depends(Provide[ApplicationContainer.rag.manager]),
) -> RAGManager:
    return manager


#
# Tools
#


@inject
def get_tool_manager(
    manager: ToolManager = Depends(Provide[ApplicationContainer.tools.manager]),
) -> ToolManager:
    return manager
