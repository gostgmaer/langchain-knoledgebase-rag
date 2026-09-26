# Router observability
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import case, func, select

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    get_scoped_container,
    require_admin,
    require_super_admin,
    require_uuid_header,
)
from packages.api.responses import ApiResponse
from packages.application.services.retention_service import purge_expired
from packages.domain.enums.document_status import DocumentStatus
from packages.domain.models.audit_event import AuditEvent
from packages.domain.models.document import Document
from packages.domain.models.message import Message
from packages.domain.models.message_citation import MessageCitation
from packages.domain.models.retrieval_log import RetrievalLog, RetrievalResultLog
from packages.infrastructure.container import ApplicationContainer
from packages.knowledge.pipelines.ingestion import PIPELINE_VERSION

router = APIRouter(
    prefix="/observability",
    tags=["Observability"],
    dependencies=[Depends(require_admin())],
)


class RetrievalSummarySchema(BaseModel):
    days: int
    retrievals: int
    avg_latency_ms: float | None
    p95_latency_ms: float | None
    avg_candidates: float | None
    avg_selected: float | None
    empty_rate: float | None
    """Share of retrievals that found no candidate at all."""
    low_confidence_rate: float | None
    """Share of retrievals whose best reranker score was below zero (weak match)."""
    answers_with_sources: int
    answers_total: int
    citation_coverage: float | None
    """Share of answers that used retrieval and cite at least one source."""


class DocumentHealthSchema(BaseModel):
    total: int
    by_status: dict[str, int]
    stale_embeddings: int
    """Documents embedded with an older pipeline or with no processing record."""
    never_retrieved: int
    current_pipeline_version: str


class ObservabilitySummarySchema(BaseModel):
    retrieval: RetrievalSummarySchema
    documents: DocumentHealthSchema


class TopDocumentSchema(BaseModel):
    document_id: UUID
    document_name: str | None
    times_retrieved: int
    times_selected: int
    avg_reranker_score: float | None


class AuditEventSchema(BaseModel):
    id: UUID
    action: str
    resource_type: str
    resource_id: UUID | None
    actor_id: UUID | None
    request_id: str | None
    detail: dict[str, Any]
    created_at: datetime


class AuditListSchema(BaseModel):
    total: int
    limit: int
    offset: int
    events: list[AuditEventSchema]


def _ratio(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


@router.get(
    "/summary",
    response_model=ApiResponse[ObservabilitySummarySchema],
    summary="Retrieval quality and document health",
    description=(
        "Operational measures for this tenant: retrieval latency, empty and low-confidence rates, "
        "citation coverage, and how many documents are failed or embedded by an outdated pipeline. "
        "These are health signals, not accuracy: measuring answer quality needs labelled questions."
    ),
)
async def summary(
    request: Request,
    days: int = Query(default=7, ge=1, le=365),
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    session = container.database.session()
    since = datetime.now(UTC) - timedelta(days=days)
    in_window = (RetrievalLog.tenant_id == tenant_id, RetrievalLog.created_at >= since)

    row = (
        await session.execute(
            select(
                func.count(),
                func.avg(RetrievalLog.latency_ms),
                func.percentile_cont(0.95).within_group(RetrievalLog.latency_ms),
                func.avg(RetrievalLog.candidate_count),
                func.avg(RetrievalLog.selected_count),
                func.count().filter(RetrievalLog.candidate_count == 0),
            ).where(*in_window)
        )
    ).one()
    retrievals = int(row[0] or 0)

    best_score = (
        select(
            RetrievalResultLog.retrieval_id.label("rid"),
            func.max(RetrievalResultLog.reranker_score).label("best"),
        )
        .where(RetrievalResultLog.tenant_id == tenant_id)
        .group_by(RetrievalResultLog.retrieval_id)
        .subquery()
    )
    low = (
        await session.execute(
            select(func.count())
            .select_from(RetrievalLog)
            .join(best_score, best_score.c.rid == RetrievalLog.id)
            .where(*in_window, best_score.c.best < 0)
        )
    ).scalar_one()

    answers_total = (
        await session.execute(
            select(func.count()).select_from(Message).where(
                Message.retrieval_id.is_not(None), Message.created_at >= since
            )
        )
    ).scalar_one()
    answers_cited = (
        await session.execute(
            select(func.count(func.distinct(MessageCitation.message_id)))
            .join(Message, Message.id == MessageCitation.message_id)
            .where(Message.retrieval_id.is_not(None), Message.created_at >= since)
        )
    ).scalar_one()

    status_rows = (
        await session.execute(
            select(Document.status, func.count())
            .where(Document.tenant_id == tenant_id, Document.is_current.is_(True), Document.is_deleted.is_(False))
            .group_by(Document.status)
        )
    ).all()
    by_status = {str(getattr(s, "value", s)): int(n) for s, n in status_rows}

    stale = (
        await session.execute(
            select(func.count()).select_from(Document).where(
                Document.tenant_id == tenant_id,
                Document.is_current.is_(True),
                Document.status == DocumentStatus.READY,
                (Document.processing_version.is_(None)) | (Document.processing_version != PIPELINE_VERSION),
            )
        )
    ).scalar_one()

    retrieved_docs = select(RetrievalResultLog.document_id).where(
        RetrievalResultLog.tenant_id == tenant_id, RetrievalResultLog.selected_for_context.is_(True)
    )
    never = (
        await session.execute(
            select(func.count()).select_from(Document).where(
                Document.tenant_id == tenant_id,
                Document.is_current.is_(True),
                Document.status == DocumentStatus.READY,
                Document.id.not_in(retrieved_docs),
            )
        )
    ).scalar_one()

    return ApiResponse(
        message="Summary retrieved.",
        data=ObservabilitySummarySchema(
            retrieval=RetrievalSummarySchema(
                days=days,
                retrievals=retrievals,
                avg_latency_ms=round(float(row[1]), 1) if row[1] is not None else None,
                p95_latency_ms=round(float(row[2]), 1) if row[2] is not None else None,
                avg_candidates=round(float(row[3]), 2) if row[3] is not None else None,
                avg_selected=round(float(row[4]), 2) if row[4] is not None else None,
                empty_rate=_ratio(int(row[5] or 0), retrievals),
                low_confidence_rate=_ratio(int(low or 0), retrievals),
                answers_with_sources=int(answers_cited or 0),
                answers_total=int(answers_total or 0),
                citation_coverage=_ratio(int(answers_cited or 0), int(answers_total or 0)),
            ),
            documents=DocumentHealthSchema(
                total=sum(by_status.values()),
                by_status=by_status,
                stale_embeddings=int(stale or 0),
                never_retrieved=int(never or 0),
                current_pipeline_version=PIPELINE_VERSION,
            ),
        ),
    )


@router.get(
    "/top-documents",
    response_model=ApiResponse[list[TopDocumentSchema]],
    summary="Most retrieved documents",
    description="Which documents retrieval surfaces most often, and how strongly they score.",
)
async def top_documents(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=50),
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    session = container.database.session()
    since = datetime.now(UTC) - timedelta(days=days)

    rows = (
        await session.execute(
            select(
                RetrievalResultLog.document_id,
                Document.file_name,
                func.count(),
                func.sum(case((RetrievalResultLog.selected_for_context.is_(True), 1), else_=0)),
                func.avg(RetrievalResultLog.reranker_score),
            )
            .join(Document, Document.id == RetrievalResultLog.document_id, isouter=True)
            .where(RetrievalResultLog.tenant_id == tenant_id, RetrievalResultLog.created_at >= since)
            .group_by(RetrievalResultLog.document_id, Document.file_name)
            .order_by(func.sum(case((RetrievalResultLog.selected_for_context.is_(True), 1), else_=0)).desc())
            .limit(limit)
        )
    ).all()

    return ApiResponse(
        message="Top documents retrieved.",
        data=[
            TopDocumentSchema(
                document_id=doc_id,
                document_name=name,
                times_retrieved=int(seen),
                times_selected=int(chosen or 0),
                avg_reranker_score=round(float(avg), 3) if avg is not None else None,
            )
            for doc_id, name, seen, chosen, avg in rows
        ],
    )


@router.get(
    "/audit",
    response_model=ApiResponse[AuditListSchema],
    summary="Audit trail",
    description="Append-only record of important operations in this tenant, newest first.",
)
async def audit_events(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None),
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)
    session = container.database.session()
    where = [AuditEvent.tenant_id == tenant_id]
    if action:
        where.append(AuditEvent.action == action)

    total = (await session.execute(select(func.count()).select_from(AuditEvent).where(*where))).scalar_one()
    rows = (
        await session.execute(
            select(AuditEvent).where(*where).order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit)
        )
    ).scalars().all()

    return ApiResponse(
        message="Audit events retrieved.",
        data=AuditListSchema(
            total=total,
            limit=limit,
            offset=offset,
            events=[
                AuditEventSchema(
                    id=e.id,
                    action=e.action,
                    resource_type=e.resource_type,
                    resource_id=e.resource_id,
                    actor_id=e.actor_id,
                    request_id=e.request_id,
                    detail=e.detail or {},
                    created_at=e.created_at,
                )
                for e in rows
            ],
        ),
    )


@router.post(
    "/retention/purge",
    response_model=ApiResponse[dict[str, int]],
    summary="Run the retention purge now",
    description=(
        "Deletes retrieval logs and audit events past the configured retention windows "
        "(RETENTION_RETRIEVAL_LOG_DAYS / RETENTION_AUDIT_DAYS). Also runs daily in the worker. "
        "Platform-wide: it applies to every tenant's expired rows, not only the caller's."
    ),
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_super_admin())],
)
async def run_retention_purge(container: ApplicationContainer = Depends(get_scoped_container)):
    return ApiResponse(
        message="Retention purge finished.",
        data=await purge_expired(container.database.session_factory()),
    )
