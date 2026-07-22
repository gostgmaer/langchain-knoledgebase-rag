# Router knowledge bases
from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    get_scoped_container,
    require_uuid_header,
)
from packages.api.responses import ApiResponse
from packages.api.schemas.kb import (
    CreateKnowledgeBaseRequestSchema,
    KnowledgeBaseListResponseSchema,
    KnowledgeBaseResponseSchema,
)
from packages.config.loader import settings
from packages.domain.enums.knowledge_base_status import KnowledgeBaseStatus
from packages.domain.models.knowledge_base import KnowledgeBase
from packages.infrastructure.container import ApplicationContainer

router = APIRouter(
    prefix="/knowledge-bases",
    tags=["Knowledge Bases"],
)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "kb"


async def _to_response(container: ApplicationContainer, kb: KnowledgeBase) -> KnowledgeBaseResponseSchema:
    document_count = await container.repositories.knowledge_base().count_documents(kb.id)
    response = KnowledgeBaseResponseSchema.model_validate(kb)
    response.document_count = document_count
    return response


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[KnowledgeBaseResponseSchema],
    summary="Create a knowledge base",
    description="Creates a new knowledge base for the calling tenant. Embedding/chunking settings are seeded from this app's own RAG config, matching the auto-provisioned default knowledge base.",
)
async def create_knowledge_base(
    payload: CreateKnowledgeBaseRequestSchema,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    knowledge_bases = container.repositories.knowledge_base()

    existing = await knowledge_bases.get_by_tenant_and_name(tenant_id, payload.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A knowledge base named '{payload.name}' already exists for this tenant.",
        )

    knowledge_base = KnowledgeBase(
        tenant_id=tenant_id,
        name=payload.name,
        slug=_slugify(payload.name),
        description=payload.description,
        status=KnowledgeBaseStatus.ACTIVE,
        embedding_provider=settings.rag.embedding_provider,
        embedding_model=settings.rag.embedding_model,
        embedding_dimension=settings.embedding.dimensions,
        chunk_size=settings.rag.chunk_size,
        chunk_overlap=settings.rag.chunk_overlap,
        is_public=payload.is_public,
    )

    created = await knowledge_bases.create(knowledge_base)

    return ApiResponse(
        message="Knowledge base created.",
        data=await _to_response(container, created),
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[KnowledgeBaseListResponseSchema],
    summary="List knowledge bases",
    description="Lists the calling tenant's knowledge bases, any status.",
)
async def list_knowledge_bases(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    knowledge_bases = container.repositories.knowledge_base()

    total = await knowledge_bases.count_by_tenant(tenant_id)
    rows = await knowledge_bases.list_by_tenant(tenant_id, limit=limit, offset=offset)

    return ApiResponse(
        message="Knowledge bases retrieved.",
        data=KnowledgeBaseListResponseSchema(
            total=total,
            limit=limit,
            offset=offset,
            knowledge_bases=[await _to_response(container, kb) for kb in rows],
        ),
    )


@router.get(
    "/{knowledge_base_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[KnowledgeBaseResponseSchema],
    summary="Fetch a knowledge base",
    description="Fetches a single knowledge base's metadata by ID.",
)
async def get_knowledge_base(
    knowledge_base_id: UUID,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    knowledge_bases = container.repositories.knowledge_base()
    knowledge_base = await knowledge_bases.get(knowledge_base_id)

    if knowledge_base is None or knowledge_base.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found.",
        )

    return ApiResponse(
        message="Knowledge base retrieved.",
        data=await _to_response(container, knowledge_base),
    )
