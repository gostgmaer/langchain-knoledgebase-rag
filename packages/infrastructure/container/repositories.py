from __future__ import annotations

from dependency_injector import containers
from dependency_injector import providers

from packages.infrastructure.repositories.agent import AgentRepository
from packages.infrastructure.repositories.conversation import ConversationRepository
from packages.infrastructure.repositories.document import DocumentRepository
from packages.infrastructure.repositories.document_chunk import DocumentChunkRepository
from packages.infrastructure.repositories.embedding import EmbeddingRepository
from packages.infrastructure.repositories.knowledge_base import KnowledgeBaseRepository
from packages.infrastructure.repositories.message import MessageRepository
from packages.infrastructure.repositories.model_profile import ModelProfileRepository
from packages.infrastructure.repositories.prompt import PromptRepository
from packages.infrastructure.repositories.tool import ToolRepository


class RepositoryContainer(
    containers.DeclarativeContainer,
):

    database = providers.DependenciesContainer()

    session = database.session

    conversation = providers.Factory(
        ConversationRepository,
        session=session,
    )

    message = providers.Factory(
        MessageRepository,
        session=session,
    )

    knowledge_base = providers.Factory(
        KnowledgeBaseRepository,
        session=session,
    )

    document = providers.Factory(
        DocumentRepository,
        session=session,
    )

    document_chunk = providers.Factory(
        DocumentChunkRepository,
        session=session,
    )

    embedding = providers.Factory(
        EmbeddingRepository,
        session=session,
    )

    prompt = providers.Factory(
        PromptRepository,
        session=session,
    )

    tool = providers.Factory(
        ToolRepository,
        session=session,
    )

    model_profile = providers.Factory(
        ModelProfileRepository,
        session=session,
    )

    agent = providers.Factory(
        AgentRepository,
        session=session,
    )