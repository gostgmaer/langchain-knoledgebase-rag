from __future__ import annotations

from functools import cached_property

from sqlalchemy.ext.asyncio import AsyncSession

from packages.infrastructure.repositories.agent import AgentRepository
from packages.infrastructure.repositories.ai_response import AIResponseRepository
from packages.infrastructure.repositories.conversation import ConversationRepository
from packages.infrastructure.repositories.document_chunk import DocumentChunkRepository
from packages.infrastructure.repositories.document import DocumentRepository
from packages.infrastructure.repositories.document_version import DocumentVersionRepository
from packages.infrastructure.repositories.embedding import EmbeddingRepository
from packages.infrastructure.repositories.knowledge_base import KnowledgeBaseRepository
from packages.infrastructure.repositories.message import MessageRepository
from packages.infrastructure.repositories.model_profile import ModelProfileRepository
from packages.infrastructure.repositories.prompt import PromptRepository
from packages.infrastructure.repositories.tool import ToolRepository
from packages.infrastructure.repositories.upload_job import UploadJobRepository


class UnitOfWork:
    """
    Coordinates a single database transaction.
    """

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session

    # ---------------------------------------------------------
    # Context Manager
    # ---------------------------------------------------------

    async def __aenter__(self) -> "UnitOfWork":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type:
                await self.session.rollback()
            else:
                await self.session.commit()
        finally:
            await self.session.close()

    # ---------------------------------------------------------
    # Transaction
    # ---------------------------------------------------------

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def flush(self) -> None:
        await self.session.flush()

    async def close(self) -> None:
        await self.session.close()

    # ---------------------------------------------------------
    # Repositories
    # ---------------------------------------------------------

    @cached_property
    def conversations(self) -> ConversationRepository:
        return ConversationRepository(self.session)

    @cached_property
    def messages(self) -> MessageRepository:
        return MessageRepository(self.session)

    @cached_property
    def knowledge_bases(self) -> KnowledgeBaseRepository:
        return KnowledgeBaseRepository(self.session)

    @cached_property
    def documents(self) -> DocumentRepository:
        return DocumentRepository(self.session)

    @cached_property
    def document_chunks(self) -> DocumentChunkRepository:
        return DocumentChunkRepository(self.session)

    @cached_property
    def embeddings(self) -> EmbeddingRepository:
        return EmbeddingRepository(self.session)

    @cached_property
    def prompts(self) -> PromptRepository:
        return PromptRepository(self.session)

    @cached_property
    def model_profiles(self) -> ModelProfileRepository:
        return ModelProfileRepository(self.session)

    @cached_property
    def tools(self) -> ToolRepository:
        return ToolRepository(self.session)

    @cached_property
    def agents(self) -> AgentRepository:
        return AgentRepository(self.session)

    @cached_property
    def document_versions(self) -> DocumentVersionRepository:
        return DocumentVersionRepository(self.session)

    @cached_property
    def upload_jobs(self) -> UploadJobRepository:
        return UploadJobRepository(self.session)

    @cached_property
    def ai_responses(self) -> AIResponseRepository:
        return AIResponseRepository(self.session)