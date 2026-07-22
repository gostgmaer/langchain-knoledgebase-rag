# Router search
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    get_scoped_container,
    require_uuid_header,
)
from packages.api.responses import ApiResponse
from packages.api.schemas.search import (
    SearchRequestSchema,
    SearchResponseSchema,
    SearchResultSchema,
)
from packages.conversation.bootstrap import ensure_default_model_profile
from packages.infrastructure.container import ApplicationContainer
from packages.knowledge.vectorstores.schema import SearchFilter, SearchOptions

router = APIRouter(
    prefix="/search",
    tags=["Search"],
)


@router.post(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[SearchResponseSchema],
    summary="Search the knowledge base directly",
    description=(
        "Runs the same hybrid retrieval + cross-encoder reranking the "
        "chat pipeline's retrieve node uses (packages/graph/nodes/"
        "retrieve.py), for callers who want raw search results instead "
        "of a chat-mediated answer. Unlike the chat path, this does not "
        "expand the query into variants — one query in, one ranked "
        "result set out."
    ),
)
async def search(
    payload: SearchRequestSchema,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    model_profiles = container.repositories.model_profile()
    model_profile = await ensure_default_model_profile(model_profiles)

    knowledge_manager = container.rag.knowledge_manager()
    reranker = container.rag.reranker()

    filters = SearchFilter(
        tenant_id=tenant_id,
        model_profile_id=model_profile.id,
        document_id=payload.document_id,
    )

    candidates = await knowledge_manager.search(
        query=payload.query,
        filters=filters,
        options=SearchOptions(limit=max(payload.limit * 2, 10)),
    )

    reranked = await reranker.rerank(payload.query, candidates, top_k=payload.limit)

    return ApiResponse(
        message="Search completed.",
        data=SearchResponseSchema(
            query=payload.query,
            results=[
                SearchResultSchema(
                    document_id=result.chunk.document_id,
                    chunk_id=result.chunk.id,
                    chunk_index=result.chunk.chunk_index,
                    content=result.chunk.content,
                    score=result.score,
                )
                for result in reranked
            ],
        ),
    )
