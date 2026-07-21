# Default KnowledgeBase provisioning
from __future__ import annotations

from uuid import UUID

from packages.config.loader import settings
from packages.domain.enums.knowledge_base_status import KnowledgeBaseStatus
from packages.domain.models.knowledge_base import KnowledgeBase
from packages.infrastructure.repositories.knowledge_base import (
    KnowledgeBaseRepository,
)

DEFAULT_NAME = "default"


async def ensure_default_knowledge_base(
    tenant_id: UUID,
    knowledge_bases: KnowledgeBaseRepository,
) -> KnowledgeBase:
    """
    Returns this tenant's default KnowledgeBase, creating one if none
    exists yet. Scoped per tenant_id, mirroring the get-or-create
    idiom in packages/conversation/bootstrap.py — KnowledgeBase has a
    required tenant_id column, so a single global default would leak
    one tenant's documents into another's search results.
    """
    existing = await knowledge_bases.get_by_tenant_and_name(
        tenant_id,
        DEFAULT_NAME,
    )
    if existing is not None:
        return existing

    knowledge_base = KnowledgeBase(
        tenant_id=tenant_id,
        name=DEFAULT_NAME,
        slug=DEFAULT_NAME,
        description="Auto-provisioned default knowledge base.",
        status=KnowledgeBaseStatus.ACTIVE,
        embedding_provider=settings.rag.embedding_provider,
        embedding_model=settings.rag.embedding_model,
        embedding_dimension=settings.embedding.dimensions,
        chunk_size=settings.rag.chunk_size,
        chunk_overlap=settings.rag.chunk_overlap,
        is_public=False,
    )

    return await knowledge_bases.create(knowledge_base)
