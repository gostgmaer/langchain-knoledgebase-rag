# API dependencies
from __future__ import annotations

from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import Depends

from packages.infrastructure.ai.manager import LLMManager
from packages.conversation.manager import ConversationManager
from packages.graph.manager import GraphManager
from packages.infrastructure.container import ApplicationContainer
from packages.memory.manager import MemoryManager
from packages.rag.manager import RAGManager
from packages.tools.manager import ToolManager


#
# Root Container
#


def get_container(
    container: Annotated[
        ApplicationContainer,
        Depends(Provide[ApplicationContainer]),
    ],
) -> ApplicationContainer:
    return container


#
# AI
#

def get_ai_manager(
    manager: Annotated[
        LLMManager,
        Depends(Provide[ApplicationContainer.ai.manager]),
    ],
) -> LLMManager:
    return manager


#
# Conversation
#


def get_conversation_manager(
    manager: Annotated[
        ConversationManager,
        Depends(Provide[ApplicationContainer.conversation.manager]),
    ],
) -> ConversationManager:
    return manager


#
# Graph
#


def get_graph_manager(
    manager: Annotated[
        GraphManager,
        Depends(Provide[ApplicationContainer.graph.manager]),
    ],
) -> GraphManager:
    return manager


#
# Memory
#


def get_memory_manager(
    manager: Annotated[
        MemoryManager,
        Depends(Provide[ApplicationContainer.memory.manager]),
    ],
) -> MemoryManager:
    return manager


#
# RAG
#


def get_rag_manager(
    manager: Annotated[
        RAGManager,
        Depends(Provide[ApplicationContainer.rag.manager]),
    ],
) -> RAGManager:
    return manager


#
# Tools
#


def get_tool_manager(
    manager: Annotated[
        ToolManager,
        Depends(Provide[ApplicationContainer.tools.manager]),
    ],
) -> ToolManager:
    return manager