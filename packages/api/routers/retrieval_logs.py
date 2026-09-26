# Router retrieval logs
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    get_scoped_container,
    require_admin,
    require_uuid_header,
)
from packages.api.responses import ApiResponse
from packages.api.schemas.retrieval_log import (
    RetrievalLogDetailSchema,
    RetrievalLogListSchema,
    RetrievalLogSummarySchema,
    RetrievalResultSchema,
)
from packages.domain.models.document import Document
from packages.domain.models.document_chunk import DocumentChunk
from packages.domain.models.document_version import DocumentVersion
from packages.domain.models.knowledge_source import KnowledgeSource
from packages.domain.models.retrieval_log import RetrievalLog, RetrievalResultLog
from packages.infrastructure.container import ApplicationContainer

router = APIRouter(
    prefix="/retrieval-logs",
    tags=["Retrieval Logs"],
    # Retrieval internals (scores, ranks, which chunks were considered) are for operators only.
    dependencies=[Depends(require_admin())],
)


def _summary(row: RetrievalLog) -> RetrievalLogSummarySchema:
    return RetrievalLogSummarySchema(
        retrieval_id=row.id,
        trace_id=row.trace_id,
        request_id=row.request_id,
        user_id=row.user_id,
        conversation_id=row.conversation_id,
        query_hash=row.query_hash,
        query_length=row.query_length,
        strategy=row.strategy,
        top_k=row.top_k,
        reranking_enabled=row.reranking_enabled,
        reranker_model=row.reranker_model,
        candidate_count=row.candidate_count,
        selected_count=row.selected_count,
        search_latency_ms=row.search_latency_ms,
        rerank_latency_ms=row.rerank_latency_ms,
        latency_ms=row.latency_ms,
        created_at=row.created_at,
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[RetrievalLogListSchema],
    summary="List retrievals",
    description="This tenant's retrieval requests, newest first. Optionally narrowed to one conversation.",
)
async def list_retrievals(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    conversation_id: UUID | None = Query(default=None),
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    session = container.database.session()

    where = [RetrievalLog.tenant_id == tenant_id, RetrievalLog.deleted_at.is_(None)]
    if conversation_id is not None:
        where.append(RetrievalLog.conversation_id == conversation_id)

    total = (await session.execute(select(func.count()).select_from(RetrievalLog).where(*where))).scalar_one()
    rows = (
        await session.execute(
            select(RetrievalLog).where(*where).order_by(RetrievalLog.created_at.desc()).offset(offset).limit(limit)
        )
    ).scalars().all()

    return ApiResponse(
        message="Retrievals retrieved.",
        data=RetrievalLogListSchema(
            total=total, limit=limit, offset=offset, retrievals=[_summary(r) for r in rows]
        ),
    )


@router.get(
    "/{retrieval_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[RetrievalLogDetailSchema],
    summary="Explain one retrieval",
    description=(
        "Every candidate chunk of one retrieval with its search score, reranker score, final rank, "
        "whether it was used as context, and where it came from (document, version, page, section, "
        "chunking method). Enough to reconstruct why an answer cited what it did."
    ),
)
async def get_retrieval(
    retrieval_id: UUID,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    session = container.database.session()

    log = (
        await session.execute(
            select(RetrievalLog).where(RetrievalLog.id == retrieval_id, RetrievalLog.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retrieval not found.")

    rows = (
        await session.execute(
            select(RetrievalResultLog, DocumentChunk, Document, DocumentVersion.version_number, KnowledgeSource.name)
            .join(DocumentChunk, DocumentChunk.id == RetrievalResultLog.chunk_id, isouter=True)
            .join(Document, Document.id == RetrievalResultLog.document_id, isouter=True)
            .join(DocumentVersion, DocumentVersion.document_id == RetrievalResultLog.document_id, isouter=True)
            .join(KnowledgeSource, KnowledgeSource.id == Document.source_id, isouter=True)
            .where(RetrievalResultLog.retrieval_id == retrieval_id, RetrievalResultLog.tenant_id == tenant_id)
            .order_by(RetrievalResultLog.retrieval_rank)
        )
    ).all()

    results = [
        RetrievalResultSchema(
            chunk_id=r.chunk_id,
            chunk_index=r.chunk_index,
            document_id=r.document_id,
            document_name=doc.file_name if doc else None,
            document_version=version,
            document_is_current=doc.is_current if doc else None,
            page_number=chunk.page_number if chunk else None,
            section=chunk.section if chunk else None,
            chunking_strategy=((chunk.metadata_ or {}).get("chunking_strategy") if chunk else None),
            source_type=(doc.source_type or "upload") if doc else None,
            source_id=doc.source_id if doc else None,
            source_name=source_name,
            canonical_url=doc.canonical_url if doc else None,
            external_version=doc.external_version if doc else None,
            sync_id=doc.sync_id if doc else None,
            retrieval_rank=r.retrieval_rank,
            retrieval_score=r.retrieval_score,
            vector_score=r.vector_score,
            keyword_score=r.keyword_score,
            reranker_score=r.reranker_score,
            final_rank=r.final_rank,
            selected_for_context=r.selected_for_context,
            reranking_changed_rank=(r.final_rank != r.retrieval_rank) if r.final_rank is not None else None,
        )
        for r, chunk, doc, version, source_name in rows
    ]

    return ApiResponse(
        message="Retrieval retrieved.",
        data=RetrievalLogDetailSchema(
            **_summary(log).model_dump(),
            model_profile_id=log.model_profile_id,
            min_relevance_score=log.min_relevance_score,
            sub_query_count=log.sub_query_count,
            filters=log.filters or {},
            results=results,
        ),
    )
