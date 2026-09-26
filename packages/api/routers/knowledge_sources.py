# Router knowledge sources
"""
Admin API for external knowledge sources: configure, test, preview, sync, monitor, and map identities.

Everything is tenant-scoped by X-Tenant-ID (a platform operator may act for another tenant, as elsewhere), every
mutation is audited, and no response ever contains a credential: credentials are write-only (PUT) and only
their status is readable.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import case, func, select

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    DEFAULT_USER_ID,
    get_scoped_container,
    require_admin,
    require_uuid_header,
)
from packages.api.responses import ApiResponse
from packages.api.schemas.knowledge_source import (
    ALLOWED_INTERVALS,
    ConnectionTestSchema,
    ConnectorTypesSchema,
    ConnectorTypeSchema,
    CredentialsSchema,
    CredentialStatusSchema,
    ExternalDocumentListSchema,
    ExternalDocumentSchema,
    IdentityMappingListSchema,
    IdentityMappingSchema,
    PreviewItemSchema,
    PreviewSchema,
    SourceCreateSchema,
    SourceHealthSchema,
    SourceListSchema,
    SourcePermissionsSchema,
    SourceResponseSchema,
    SourcesSummarySchema,
    SourceUpdateSchema,
    SyncRequestSchema,
    SyncRunDetailSchema,
    SyncRunListSchema,
    SyncRunSchema,
    TestConnectionSchema,
    UnmappedPrincipalSchema,
    ValidationSchema,
)
from packages.config.loader import settings
from packages.connectors.access import remap_access
from packages.connectors.base import validate_against_schema
from packages.connectors.common import COMMON_FIELDS, split_config
from packages.connectors.credential_service import SourceCredentialService
from packages.connectors.credentials import CredentialConfigurationError, CredentialDecryptionError
from packages.connectors.http import AuthenticationFailed, ConnectorHttpError
from packages.connectors.models import DiscoveryContext
from packages.connectors.registry import default_registry
from packages.connectors import webhooks
from packages.connectors.scheduling import (
    SourceNotSyncable,
    SyncAlreadyRunning,
    add_pending_targets,
    create_run,
    dispatch,
    request_cancel,
)
from packages.domain.enums.document_status import DocumentStatus
from packages.domain.models.document import Document
from packages.domain.models.document_chunk import DocumentChunk
from packages.domain.models.knowledge_source import (
    DocumentAccessRule,
    ExternalDocumentRecord,
    IdentityMapping,
    KnowledgeSource,
    SourceSyncRun,
)
from packages.infrastructure.container import ApplicationContainer
from packages.knowledge.pipelines.ingestion import PIPELINE_VERSION  # noqa: F401 - re-exported for parity with other routers
from packages.sdk.iam.models import CurrentUser  # noqa: F401

router = APIRouter(prefix="/knowledge-sources", tags=["Knowledge Sources"], dependencies=[Depends(require_admin())])
webhook_router = APIRouter(prefix="/webhooks", tags=["Knowledge Sources"])

_credentials = SourceCredentialService()
_registry = default_registry()


# ====================================================================== helpers
def _ids(request: Request) -> tuple[UUID, UUID]:
    return (
        require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID),
        require_uuid_header(request, "X-User-ID", default=DEFAULT_USER_ID),
    )


async def _get_source(session, tenant_id: UUID, source_id: UUID) -> KnowledgeSource:
    source = await session.get(KnowledgeSource, source_id)
    if source is None or source.tenant_id != tenant_id or source.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge source not found.")
    return source


def _label(source_type: str) -> str:
    for info in _registry.infos():
        if info.type == source_type:
            return info.display_name
    return source_type


async def _check_config(source_type: str, configuration: dict[str, Any], credentials: dict[str, Any] | None, *, check_credentials: bool = True):
    """Validation without touching the network: common settings, connector settings and (optionally) credential shape."""
    if not _registry.is_available(source_type):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"'{source_type}' is not an available connector.")
    common, specific = split_config(configuration or {})
    errors = list(validate_against_schema(COMMON_FIELDS, common).errors)
    connector = _registry.create(source_type, specific, credentials, allow_private=settings.rag.connector_allow_private_hosts)
    errors += (await connector.validate_settings()).errors
    if check_credentials:
        errors += (await connector.validate_credentials()).errors
    return errors, connector


def _check_schedule(sync_mode: str, interval: int | None) -> None:
    if sync_mode == "scheduled":
        if interval not in ALLOWED_INTERVALS:
            raise HTTPException(status_code=422, detail=f"Choose a schedule of {', '.join(str(i) for i in ALLOWED_INTERVALS)} minutes.")


def _webhook_hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


async def _counts(session, tenant_id: UUID, source_ids: list[UUID]) -> dict[UUID, tuple[int, int]]:
    if not source_ids:
        return {}
    rows = (
        await session.execute(
            select(
                ExternalDocumentRecord.source_id,
                func.count().filter(ExternalDocumentRecord.status.in_(("indexed", "updated"))),
                func.count().filter(ExternalDocumentRecord.status == "failed"),
            )
            .where(ExternalDocumentRecord.tenant_id == tenant_id, ExternalDocumentRecord.source_id.in_(source_ids))
            .group_by(ExternalDocumentRecord.source_id)
        )
    ).all()
    return {sid: (int(ok), int(bad)) for sid, ok, bad in rows}


async def _response(session, source: KnowledgeSource, counts: dict[UUID, tuple[int, int]], *, webhook_secret: str | None = None) -> SourceResponseSchema:
    # Server-side defaults (updated_at) are expired by a flush; reload them here rather than lazily in a sync accessor.
    await session.flush()  # a refresh would otherwise discard pending edits
    await session.refresh(source)
    indexed, failed = counts.get(source.id, (0, 0))
    cred = await _credentials.status(session, source)
    health = source.health or {}
    return SourceResponseSchema(
        id=source.id, name=source.name, type=source.type, type_label=_label(source.type), description=source.description,
        status=source.status, sync_mode=source.sync_mode, sync_interval_minutes=source.sync_interval_minutes,
        last_sync_at=source.last_sync_at, next_sync_at=source.next_sync_at,
        last_successful_sync_at=source.last_successful_sync_at, last_sync_status=source.last_sync_status,
        configuration=source.configuration or {}, knowledge_base_id=source.knowledge_base_id,
        credential=CredentialStatusSchema(**cred), document_count=indexed, failed_count=failed,
        health={k: health.get(k) for k in ("connection", "authentication", "last_sync_seconds", "checked_at") if k in health},
        webhook_enabled=bool(source.webhook_secret_hash), webhook_secret=webhook_secret,
        created_at=source.created_at, updated_at=source.updated_at,
    )


def _credential_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


# ====================================================================== catalogue and summary
@router.get("/types", response_model=ApiResponse[ConnectorTypesSchema], summary="Connector types and their settings")
async def list_types():
    return ApiResponse(
        message="Connector types retrieved.",
        data=ConnectorTypesSchema(
            types=[
                ConnectorTypeSchema(
                    type=i.type, display_name=i.display_name, description=i.description, icon=i.icon, available=i.available,
                    credential_kind=i.credential_kind, credential_fields=i.credential_fields, config_schema=i.config_schema,
                    supports_permissions=i.supports_permissions, supports_changes=i.supports_changes, notes=i.notes,
                )
                for i in _registry.infos()
            ],
            common_fields=[f.to_dict() for f in COMMON_FIELDS],
            sync_intervals=[
                {"minutes": 15, "label": "Every 15 minutes"}, {"minutes": 30, "label": "Every 30 minutes"},
                {"minutes": 60, "label": "Hourly"}, {"minutes": 1440, "label": "Daily"}, {"minutes": 10080, "label": "Weekly"},
            ],
        ),
    )


@router.get("/summary", response_model=ApiResponse[SourcesSummarySchema], summary="Aggregate source health")
async def summary(request: Request, container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, _ = _ids(request)
    session = container.database.session()
    by_status = dict(
        (await session.execute(select(KnowledgeSource.status, func.count()).where(KnowledgeSource.tenant_id == tenant_id, KnowledgeSource.is_deleted.is_(False)).group_by(KnowledgeSource.status))).all()
    )
    total_sources = sum(by_status.values())
    docs = (
        await session.execute(
            select(
                func.count().filter(ExternalDocumentRecord.status.in_(("indexed", "updated"))),
                func.count().filter(ExternalDocumentRecord.status == "failed"),
            ).where(ExternalDocumentRecord.tenant_id == tenant_id)
        )
    ).one()
    chunks = (
        await session.execute(
            select(func.count()).select_from(DocumentChunk).join(Document, Document.id == DocumentChunk.document_id).where(
                Document.tenant_id == tenant_id, Document.source_id.is_not(None), Document.is_current.is_(True), Document.status == DocumentStatus.READY, DocumentChunk.chunk_index >= 0,
            )
        )
    ).scalar_one()
    midnight = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today = (
        await session.execute(
            select(func.coalesce(func.sum(SourceSyncRun.documents_created), 0), func.coalesce(func.sum(SourceSyncRun.documents_updated), 0), func.coalesce(func.sum(SourceSyncRun.documents_deleted), 0))
            .where(SourceSyncRun.tenant_id == tenant_id, SourceSyncRun.started_at >= midnight)
        )
    ).one()
    last = (
        await session.execute(
            select(SourceSyncRun.started_at, SourceSyncRun.completed_at).where(SourceSyncRun.tenant_id == tenant_id, SourceSyncRun.completed_at.is_not(None)).order_by(SourceSyncRun.completed_at.desc()).limit(1)
        )
    ).first()
    stale = (
        await session.execute(
            select(func.count()).select_from(ExternalDocumentRecord).where(
                ExternalDocumentRecord.tenant_id == tenant_id, ExternalDocumentRecord.status.in_(("indexed", "updated")),
                ExternalDocumentRecord.external_updated_at.is_not(None), ExternalDocumentRecord.last_indexed_at.is_not(None),
                ExternalDocumentRecord.external_updated_at > ExternalDocumentRecord.last_indexed_at,
            )
        )
    ).scalar_one()
    return ApiResponse(
        message="Summary retrieved.",
        data=SourcesSummarySchema(
            total_sources=total_sources,
            connected_sources=by_status.get("active", 0),
            disconnected_sources=by_status.get("disconnected", 0),
            sources_with_errors=by_status.get("error", 0),
            paused_sources=by_status.get("paused", 0),
            total_documents=int(docs[0] or 0), total_chunks=int(chunks or 0),
            documents_added_today=int(today[0]), documents_updated_today=int(today[1]), documents_deleted_today=int(today[2]),
            failed_documents=int(docs[1] or 0),
            last_sync_duration_seconds=round((last[1] - last[0]).total_seconds(), 1) if last and last[0] and last[1] else None,
            stale_documents=int(stale or 0),
        ),
    )


# ====================================================================== identity mappings
@router.get("/identity-mappings", response_model=ApiResponse[IdentityMappingListSchema], summary="External identity mappings")
async def list_mappings(request: Request, provider: str | None = Query(default=None), container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, _ = _ids(request)
    stmt = select(IdentityMapping).where(IdentityMapping.tenant_id == tenant_id).order_by(IdentityMapping.provider, IdentityMapping.external_id)
    if provider:
        stmt = stmt.where(IdentityMapping.provider == provider)
    rows = (await container.database.session().execute(stmt)).scalars().all()
    return ApiResponse(
        message="Mappings retrieved.",
        data=IdentityMappingListSchema(mappings=[IdentityMappingSchema(id=m.id, provider=m.provider, principal_type=m.principal_type, external_id=m.external_id, internal_type=m.internal_type, internal_id=m.internal_id) for m in rows]),
    )


@router.put("/identity-mappings", response_model=ApiResponse[IdentityMappingSchema], summary="Map an external user or group to an internal user or role")
async def upsert_mapping(payload: IdentityMappingSchema, request: Request, container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, user_id = _ids(request)
    if not _registry.is_available(payload.provider):
        raise HTTPException(status_code=422, detail=f"Unknown provider '{payload.provider}'.")
    session = container.database.session()
    row = (
        await session.execute(
            select(IdentityMapping).where(IdentityMapping.tenant_id == tenant_id, IdentityMapping.provider == payload.provider, IdentityMapping.principal_type == payload.principal_type, IdentityMapping.external_id == payload.external_id)
        )
    ).scalar_one_or_none()
    if row is None:
        row = IdentityMapping(tenant_id=tenant_id, provider=payload.provider, principal_type=payload.principal_type, external_id=payload.external_id, created_by=user_id, internal_type=payload.internal_type, internal_id=payload.internal_id)
        session.add(row)
    else:
        row.internal_type, row.internal_id = payload.internal_type, payload.internal_id
    await session.flush()
    changed = await remap_access(session, tenant_id=tenant_id, provider=payload.provider)
    await container.audit().record(
        tenant_id=tenant_id, actor_id=user_id, action="source.permissions_changed", resource_type="identity_mapping", resource_id=row.id,
        detail={"provider": payload.provider, "principal_type": payload.principal_type, "internal_type": payload.internal_type, "documents_updated": changed},
    )
    return ApiResponse(message="Mapping saved.", data=IdentityMappingSchema(id=row.id, provider=row.provider, principal_type=row.principal_type, external_id=row.external_id, internal_type=row.internal_type, internal_id=row.internal_id))


@router.delete("/identity-mappings/{mapping_id}", response_model=ApiResponse[None], summary="Remove an identity mapping")
async def delete_mapping(mapping_id: UUID, request: Request, container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, user_id = _ids(request)
    session = container.database.session()
    row = await session.get(IdentityMapping, mapping_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Mapping not found.")
    provider = row.provider
    await session.delete(row)
    await session.flush()
    changed = await remap_access(session, tenant_id=tenant_id, provider=provider)
    await container.audit().record(tenant_id=tenant_id, actor_id=user_id, action="source.permissions_changed", resource_type="identity_mapping", resource_id=mapping_id, detail={"provider": provider, "removed": True, "documents_updated": changed})
    return ApiResponse(message="Mapping removed.")


# ====================================================================== connection test (unsaved)
@router.post("/test", response_model=ApiResponse[ConnectionTestSchema], summary="Validate and test a configuration before saving it")
async def test_unsaved(payload: TestConnectionSchema, container: ApplicationContainer = Depends(get_scoped_container)):
    errors, connector = await _check_config(payload.type, payload.configuration, payload.credentials)
    validation = ValidationSchema(ok=not errors, errors=errors)
    if errors:
        return ApiResponse(message="Configuration is not valid.", data=ConnectionTestSchema(ok=False, message="; ".join(errors), validation=validation))
    try:
        result = await connector.test_connection()
    except (ConnectorHttpError, OSError) as exc:
        result = None
        message = str(exc)
    finally:
        await connector.aclose()
    if result is None:
        return ApiResponse(message="Connection failed.", data=ConnectionTestSchema(ok=False, message=message, validation=validation))
    return ApiResponse(message="Connection tested.", data=ConnectionTestSchema(ok=result.ok, message=result.message, authenticated=result.authenticated, details=result.details, validation=validation))


# ====================================================================== CRUD
@router.post("", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[SourceResponseSchema], summary="Create a knowledge source (paused until you start the first sync)")
async def create_source(payload: SourceCreateSchema, request: Request, container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, user_id = _ids(request)
    errors, connector = await _check_config(payload.type, payload.configuration, payload.credentials, check_credentials=payload.credentials is not None)
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))
    _check_schedule(payload.sync_mode, payload.sync_interval_minutes)
    needs_secret = connector.credential_kind != "none"
    await connector.aclose()

    session = container.database.session()
    duplicate = (await session.execute(select(KnowledgeSource.id).where(KnowledgeSource.tenant_id == tenant_id, KnowledgeSource.name == payload.name, KnowledgeSource.is_deleted.is_(False)))).first()
    if duplicate:
        raise HTTPException(status_code=409, detail=f"A source named '{payload.name}' already exists.")

    webhook_secret = secrets.token_urlsafe(32) if payload.sync_mode in ("webhook", "realtime") else None
    source = KnowledgeSource(
        tenant_id=tenant_id, knowledge_base_id=payload.knowledge_base_id, name=payload.name, type=payload.type, description=payload.description,
        status="paused",  # nothing is ingested until the administrator confirms
        sync_mode=payload.sync_mode, sync_interval_minutes=payload.sync_interval_minutes if payload.sync_mode == "scheduled" else None,
        configuration=payload.configuration, created_by=user_id, webhook_secret_hash=_webhook_hash(webhook_secret) if webhook_secret else None,
        health={"connection": "unknown", "authentication": "unknown"},
    )
    session.add(source)
    await session.flush()

    if payload.credentials and needs_secret:
        try:
            await _credentials.store(session, source, kind=_registry.get(payload.type).credential_kind, secret=payload.credentials, actor_id=user_id)
        except CredentialConfigurationError as exc:
            raise _credential_error(exc) from exc
        await container.audit().record(tenant_id=tenant_id, actor_id=user_id, action="source.credentials_connected", resource_type="knowledge_source", resource_id=source.id, detail={"source_name": source.name})

    await container.audit().record(tenant_id=tenant_id, actor_id=user_id, action="source.created", resource_type="knowledge_source", resource_id=source.id, detail={"source_name": source.name, "type": source.type, "sync_mode": source.sync_mode})
    return ApiResponse(message="Knowledge source created.", data=await _response(session, source, {}, webhook_secret=webhook_secret))


@router.get("", response_model=ApiResponse[SourceListSchema], summary="List knowledge sources")
async def list_sources(request: Request, container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, _ = _ids(request)
    session = container.database.session()
    rows = (await session.execute(select(KnowledgeSource).where(KnowledgeSource.tenant_id == tenant_id, KnowledgeSource.is_deleted.is_(False)).order_by(KnowledgeSource.name))).scalars().all()
    counts = await _counts(session, tenant_id, [s.id for s in rows])
    return ApiResponse(message="Sources retrieved.", data=SourceListSchema(total=len(rows), sources=[await _response(session, s, counts) for s in rows]))


@router.get("/{source_id}", response_model=ApiResponse[SourceResponseSchema], summary="One knowledge source")
async def get_source(source_id: UUID, request: Request, container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, _ = _ids(request)
    session = container.database.session()
    source = await _get_source(session, tenant_id, source_id)
    return ApiResponse(message="Source retrieved.", data=await _response(session, source, await _counts(session, tenant_id, [source.id])))


@router.patch("/{source_id}", response_model=ApiResponse[SourceResponseSchema], summary="Edit a knowledge source")
async def update_source(source_id: UUID, payload: SourceUpdateSchema, request: Request, container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, user_id = _ids(request)
    session = container.database.session()
    source = await _get_source(session, tenant_id, source_id)
    audit = container.audit()
    changed: list[str] = []

    if payload.configuration is not None:
        # Credentials are validated where they are set (PUT /credentials); editing settings checks the settings only.
        errors, connector = await _check_config(source.type, payload.configuration, None, check_credentials=False)
        await connector.aclose()
        if errors:
            raise HTTPException(status_code=422, detail="; ".join(errors))
        old_common, old_specific = split_config(source.configuration or {})
        new_common, new_specific = split_config(payload.configuration)
        source.configuration = payload.configuration
        if old_specific != new_specific:
            await audit.record(tenant_id=tenant_id, actor_id=user_id, action="source.content_selection_changed", resource_type="knowledge_source", resource_id=source.id, detail={"source_name": source.name})
        if old_common != new_common:
            await audit.record(tenant_id=tenant_id, actor_id=user_id, action="source.permissions_changed", resource_type="knowledge_source", resource_id=source.id, detail={"source_name": source.name, "fields": sorted(k for k in set(old_common) | set(new_common) if old_common.get(k) != new_common.get(k))})
        changed.append("configuration")
    if payload.name is not None and payload.name != source.name:
        source.name = payload.name
        changed.append("name")
    if payload.description is not None:
        source.description = payload.description
        changed.append("description")
    if payload.sync_mode is not None or payload.sync_interval_minutes is not None:
        mode = payload.sync_mode or source.sync_mode
        interval = payload.sync_interval_minutes if payload.sync_interval_minutes is not None else source.sync_interval_minutes
        _check_schedule(mode, interval)
        source.sync_mode, source.sync_interval_minutes = mode, interval if mode == "scheduled" else None
        source.next_sync_at = datetime.now(UTC) + timedelta(minutes=interval) if mode == "scheduled" and source.status == "active" else None
        changed.append("schedule")
    webhook_secret = None
    if source.sync_mode in ("webhook", "realtime") and not source.webhook_secret_hash:
        webhook_secret = secrets.token_urlsafe(32)
        source.webhook_secret_hash = _webhook_hash(webhook_secret)
    await session.flush()
    if changed:
        await audit.record(tenant_id=tenant_id, actor_id=user_id, action="source.updated", resource_type="knowledge_source", resource_id=source.id, detail={"source_name": source.name, "fields": changed})
    return ApiResponse(message="Knowledge source updated.", data=await _response(session, source, await _counts(session, tenant_id, [source.id]), webhook_secret=webhook_secret))


@router.delete("/{source_id}", response_model=ApiResponse[None], summary="Delete a source (its documents are archived, credentials destroyed)")
async def delete_source(source_id: UUID, request: Request, container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, user_id = _ids(request)
    # request_cancel runs in its own transaction and closes the shared session, so do it before loading the source:
    # edits to an object loaded earlier would be made on a detached instance and silently lost.
    await request_cancel(container, source_id, tenant_id)
    session = container.database.session()
    source = await _get_source(session, tenant_id, source_id)
    documents = (await session.execute(select(Document).where(Document.tenant_id == tenant_id, Document.source_id == source.id, Document.status != DocumentStatus.ARCHIVED))).scalars().all()
    for document in documents:
        document.status = DocumentStatus.ARCHIVED  # out of retrieval; the rows and chunks stay for audit and version history
    await _credentials.revoke(session, source)
    for record in (await session.execute(select(ExternalDocumentRecord).where(ExternalDocumentRecord.source_id == source.id))).scalars():
        record.status = "deleted"
    source.is_deleted, source.deleted_at, source.status = True, datetime.now(UTC), "disconnected"
    await container.audit().record(tenant_id=tenant_id, actor_id=user_id, action="source.deleted", resource_type="knowledge_source", resource_id=source.id, detail={"source_name": source.name, "documents_archived": len(documents)})
    return ApiResponse(message="Knowledge source deleted.")


# ====================================================================== credentials
@router.put("/{source_id}/credentials", response_model=ApiResponse[CredentialStatusSchema], summary="Set or rotate the source's credentials (write-only)")
async def set_credentials(source_id: UUID, payload: CredentialsSchema, request: Request, container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, user_id = _ids(request)
    session = container.database.session()
    source = await _get_source(session, tenant_id, source_id)
    connector_class = _registry.get(source.type)
    if connector_class.credential_kind == "none":
        raise HTTPException(status_code=422, detail="This connector does not use credentials.")
    _, specific = split_config(source.configuration or {})
    connector = connector_class(specific, payload.credentials)
    result = await connector.validate_credentials()
    await connector.aclose()
    if not result.ok:
        raise HTTPException(status_code=422, detail="; ".join(result.errors))
    try:
        await _credentials.store(session, source, kind=connector_class.credential_kind, secret=payload.credentials, actor_id=user_id)
    except CredentialConfigurationError as exc:
        raise _credential_error(exc) from exc
    if source.status == "disconnected":
        source.status = "paused"  # credentials replaced: let the administrator test and resume
    await container.audit().record(tenant_id=tenant_id, actor_id=user_id, action="source.credentials_connected", resource_type="knowledge_source", resource_id=source.id, detail={"source_name": source.name})
    return ApiResponse(message="Credentials saved.", data=CredentialStatusSchema(**await _credentials.status(session, source)))


@router.delete("/{source_id}/credentials", response_model=ApiResponse[CredentialStatusSchema], summary="Revoke the source's credentials")
async def revoke_credentials(source_id: UUID, request: Request, container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, user_id = _ids(request)
    session = container.database.session()
    source = await _get_source(session, tenant_id, source_id)
    await _credentials.revoke(session, source)
    source.status = "disconnected"
    source.health = {**(source.health or {}), "authentication": "revoked", "connection": "disconnected"}
    await container.audit().record(tenant_id=tenant_id, actor_id=user_id, action="source.credentials_revoked", resource_type="knowledge_source", resource_id=source.id, detail={"source_name": source.name})
    return ApiResponse(message="Credentials revoked.", data=CredentialStatusSchema(**await _credentials.status(session, source)))


# ====================================================================== test, preview, sync control
async def _connector_for(session, source: KnowledgeSource):
    connector_class = _registry.get(source.type)
    secret = None
    if connector_class.credential_kind != "none":
        try:
            secret = await _credentials.load(session, source)
        except (CredentialConfigurationError, CredentialDecryptionError) as exc:
            raise _credential_error(exc) from exc
        if secret is None:
            raise HTTPException(status_code=409, detail="No credentials are configured for this source.")
    _, specific = split_config(source.configuration or {})
    return connector_class(specific, secret, allow_private=settings.rag.connector_allow_private_hosts)


@router.post("/{source_id}/test-connection", response_model=ApiResponse[ConnectionTestSchema], summary="Test the saved connection")
async def test_saved(source_id: UUID, request: Request, container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, _ = _ids(request)
    session = container.database.session()
    source = await _get_source(session, tenant_id, source_id)
    connector = await _connector_for(session, source)
    try:
        result = await connector.test_connection()
    except ConnectorHttpError as exc:
        return ApiResponse(message="Connection failed.", data=ConnectionTestSchema(ok=False, message=str(exc)))
    finally:
        await connector.aclose()
    source.health = {**(source.health or {}), "connection": "healthy" if result.ok else "error", "authentication": "valid" if result.authenticated else ("invalid" if result.authenticated is False else (source.health or {}).get("authentication", "unknown")), "checked_at": datetime.now(UTC).isoformat()}
    return ApiResponse(message="Connection tested.", data=ConnectionTestSchema(ok=result.ok, message=result.message, authenticated=result.authenticated, details=result.details))


@router.post("/{source_id}/preview", response_model=ApiResponse[PreviewSchema], summary="List what a sync would ingest (nothing is stored)")
async def preview(source_id: UUID, request: Request, limit: int = Query(default=20, ge=1, le=50), container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, _ = _ids(request)
    session = container.database.session()
    source = await _get_source(session, tenant_id, source_id)
    connector = await _connector_for(session, source)
    items: list[PreviewItemSchema] = []
    truncated = False
    try:
        context = DiscoveryContext(source_id=source.id, tenant_id=tenant_id, limit=limit + 1)
        async for document in connector.discover(context):
            if len(items) >= limit:
                truncated = True
                break
            meta = {k: v for k, v in document.metadata.items() if isinstance(v, (str, int, float, bool)) and k not in ("etag", "last_modified", "download")}
            items.append(PreviewItemSchema(external_id=document.external_id, title=document.title, url=document.canonical_url, version=document.external_version, updated_at=document.updated_at, metadata=dict(list(meta.items())[:8])))
        warnings = list(connector.health_stats().get("warnings", []))
    except AuthenticationFailed as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ConnectorHttpError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        await connector.aclose()
    return ApiResponse(message="Preview ready.", data=PreviewSchema(items=items, truncated=truncated, warnings=warnings))


@router.post("/{source_id}/sync", status_code=status.HTTP_202_ACCEPTED, response_model=ApiResponse[SyncRunSchema], summary="Start a sync now")
async def start_sync(source_id: UUID, request: Request, background_tasks: BackgroundTasks, payload: SyncRequestSchema | None = None, container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, user_id = _ids(request)
    session = container.database.session()
    source = await _get_source(session, tenant_id, source_id)
    if payload and payload.activate and source.status in ("paused", "error", "disconnected"):
        source.status = "active"
        if source.sync_mode == "scheduled" and source.sync_interval_minutes:
            source.next_sync_at = datetime.now(UTC) + timedelta(minutes=source.sync_interval_minutes)
    await session.commit()  # the run below reads the source in its own session
    try:
        run_id = await create_run(container, source_id, tenant_id, trigger="manual", actor_id=user_id)
    except SyncAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SourceNotSyncable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await dispatch(container, background_tasks, source_id, run_id)
    await container.audit().record(tenant_id=tenant_id, actor_id=user_id, action="source.sync_requested", resource_type="knowledge_source", resource_id=source_id, detail={"sync_id": str(run_id), "trigger": "manual"})
    run = await container.database.session().get(SourceSyncRun, run_id)
    return ApiResponse(message="Sync queued.", data=_run_schema(run))


@router.post("/{source_id}/sync/cancel", response_model=ApiResponse[None], summary="Stop the running sync (between documents)")
async def cancel_sync(source_id: UUID, request: Request, container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, user_id = _ids(request)
    await _get_source(container.database.session(), tenant_id, source_id)
    if not await request_cancel(container, source_id, tenant_id):
        raise HTTPException(status_code=409, detail="No sync is running for this source.")
    await container.audit().record(tenant_id=tenant_id, actor_id=user_id, action="source.sync_cancel_requested", resource_type="knowledge_source", resource_id=source_id, detail={})
    return ApiResponse(message="Cancellation requested.")


@router.post("/{source_id}/pause", response_model=ApiResponse[SourceResponseSchema], summary="Pause syncing")
async def pause_source(source_id: UUID, request: Request, container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, user_id = _ids(request)
    session = container.database.session()
    source = await _get_source(session, tenant_id, source_id)
    source.status, source.next_sync_at = "paused", None
    await container.audit().record(tenant_id=tenant_id, actor_id=user_id, action="source.updated", resource_type="knowledge_source", resource_id=source.id, detail={"source_name": source.name, "fields": ["status:paused"]})
    return ApiResponse(message="Source paused.", data=await _response(session, source, await _counts(session, tenant_id, [source.id])))


@router.post("/{source_id}/resume", response_model=ApiResponse[SourceResponseSchema], summary="Resume syncing")
async def resume_source(source_id: UUID, request: Request, container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, user_id = _ids(request)
    session = container.database.session()
    source = await _get_source(session, tenant_id, source_id)
    source.status = "active"
    if source.sync_mode == "scheduled" and source.sync_interval_minutes:
        source.next_sync_at = datetime.now(UTC)
    await container.audit().record(tenant_id=tenant_id, actor_id=user_id, action="source.updated", resource_type="knowledge_source", resource_id=source.id, detail={"source_name": source.name, "fields": ["status:active"]})
    return ApiResponse(message="Source resumed.", data=await _response(session, source, await _counts(session, tenant_id, [source.id])))


# ====================================================================== history, documents, health, permissions
def _run_schema(run: SourceSyncRun) -> SyncRunSchema:
    duration = (run.completed_at - run.started_at).total_seconds() if run.completed_at and run.started_at else None
    return SyncRunSchema(
        id=run.id, source_id=run.source_id, trigger=run.trigger, status=run.status, started_at=run.started_at, completed_at=run.completed_at,
        duration_seconds=round(duration, 2) if duration is not None else None, documents_discovered=run.documents_discovered,
        documents_created=run.documents_created, documents_updated=run.documents_updated, documents_deleted=run.documents_deleted,
        documents_skipped=run.documents_skipped, documents_failed=run.documents_failed, permissions_updated=run.permissions_updated,
        error_count=run.error_count, error_summary=run.error_summary, trace_id=run.trace_id, request_id=run.request_id, stats=run.stats or {},
    )


@router.get("/{source_id}/runs", response_model=ApiResponse[SyncRunListSchema], summary="Sync history")
async def list_runs(source_id: UUID, request: Request, limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0), container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, _ = _ids(request)
    session = container.database.session()
    await _get_source(session, tenant_id, source_id)
    where = (SourceSyncRun.source_id == source_id, SourceSyncRun.tenant_id == tenant_id)
    total = (await session.execute(select(func.count()).select_from(SourceSyncRun).where(*where))).scalar_one()
    rows = (await session.execute(select(SourceSyncRun).where(*where).order_by(SourceSyncRun.created_at.desc()).offset(offset).limit(limit))).scalars().all()
    return ApiResponse(message="Sync history retrieved.", data=SyncRunListSchema(total=total, limit=limit, offset=offset, runs=[_run_schema(r) for r in rows]))


@router.get("/{source_id}/runs/{run_id}", response_model=ApiResponse[SyncRunDetailSchema], summary="One sync run, with its errors")
async def get_run(source_id: UUID, run_id: UUID, request: Request, container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, _ = _ids(request)
    session = container.database.session()
    run = await session.get(SourceSyncRun, run_id)
    if run is None or run.source_id != source_id or run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Sync run not found.")
    return ApiResponse(message="Sync run retrieved.", data=SyncRunDetailSchema(**_run_schema(run).model_dump(), errors=run.errors or []))


@router.get("/{source_id}/documents", response_model=ApiResponse[ExternalDocumentListSchema], summary="Documents indexed from this source")
async def list_documents(
    source_id: UUID, request: Request, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
    doc_status: str | None = Query(default=None, alias="status"), q: str | None = Query(default=None, max_length=200),
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id, _ = _ids(request)
    session = container.database.session()
    await _get_source(session, tenant_id, source_id)
    where = [ExternalDocumentRecord.source_id == source_id, ExternalDocumentRecord.tenant_id == tenant_id]
    if doc_status:
        where.append(ExternalDocumentRecord.status == doc_status)
    if q:
        where.append(ExternalDocumentRecord.title.ilike(f"%{q}%"))
    total = (await session.execute(select(func.count()).select_from(ExternalDocumentRecord).where(*where))).scalar_one()
    rows = (await session.execute(select(ExternalDocumentRecord).where(*where).order_by(ExternalDocumentRecord.title).offset(offset).limit(limit))).scalars().all()

    def freshness(r: ExternalDocumentRecord) -> int | None:
        if r.external_updated_at and r.last_indexed_at:
            return max(0, int((r.last_indexed_at - r.external_updated_at).total_seconds()))
        return None

    return ApiResponse(
        message="Documents retrieved.",
        data=ExternalDocumentListSchema(
            total=total, limit=limit, offset=offset,
            documents=[
                ExternalDocumentSchema(
                    id=r.id, external_id=r.external_id, title=r.title, canonical_url=r.canonical_url, status=r.status, document_id=r.document_id,
                    external_version=r.external_version, external_updated_at=r.external_updated_at, last_synced_at=r.last_synced_at,
                    last_indexed_at=r.last_indexed_at, freshness_seconds=freshness(r), failure_count=r.failure_count, last_error=r.last_error,
                    metadata={k: v for k, v in (r.metadata_ or {}).items() if isinstance(v, (str, int, float, bool)) and k not in ("etag", "last_modified")},
                )
                for r in rows
            ],
        ),
    )


@router.post("/{source_id}/documents/{record_id}/retry", response_model=ApiResponse[None], summary="Clear a document's failure count so the next sync retries it")
async def retry_document(source_id: UUID, record_id: UUID, request: Request, container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, _ = _ids(request)
    session = container.database.session()
    record = await session.get(ExternalDocumentRecord, record_id)
    if record is None or record.source_id != source_id or record.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Document not found.")
    record.failure_count, record.external_version = 0, None  # forgetting the version forces a fresh fetch next sync
    return ApiResponse(message="The document will be retried on the next sync.")


@router.get("/{source_id}/health", response_model=ApiResponse[SourceHealthSchema], summary="Connection health of one source")
async def source_health(source_id: UUID, request: Request, container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, _ = _ids(request)
    session = container.database.session()
    source = await _get_source(session, tenant_id, source_id)
    counts = (await session.execute(select(func.count(), func.count().filter(ExternalDocumentRecord.status.in_(("indexed", "updated"))), func.count().filter(ExternalDocumentRecord.status == "failed")).where(ExternalDocumentRecord.source_id == source_id, ExternalDocumentRecord.status != "deleted"))).one()
    last_failed = (await session.execute(select(SourceSyncRun).where(SourceSyncRun.source_id == source_id, SourceSyncRun.status == "failed").order_by(SourceSyncRun.created_at.desc()).limit(1))).scalars().first()
    durations = [(r.completed_at - r.started_at).total_seconds() for r in (await session.execute(select(SourceSyncRun).where(SourceSyncRun.source_id == source_id, SourceSyncRun.status.in_(("succeeded", "partial")), SourceSyncRun.completed_at.is_not(None)).order_by(SourceSyncRun.created_at.desc()).limit(10))).scalars() if r.started_at and r.completed_at]
    health = source.health or {}
    latest = (await session.execute(select(SourceSyncRun).where(SourceSyncRun.source_id == source_id).order_by(SourceSyncRun.created_at.desc()).limit(1))).scalars().first()
    stats = (latest.stats if latest else None) or {}
    warnings = list((stats.get("crawl") or {}).get("warnings", []))[:10] if isinstance(stats.get("crawl"), dict) else []
    return ApiResponse(
        message="Health retrieved.",
        data=SourceHealthSchema(
            connection=health.get("connection", "unknown"), authentication=health.get("authentication", "unknown"),
            last_successful_sync_at=source.last_successful_sync_at, last_failed_sync_at=last_failed.completed_at if last_failed else None,
            last_failure=last_failed.error_summary if last_failed else None, avg_sync_seconds=round(sum(durations) / len(durations), 1) if durations else None,
            documents_discovered=int(counts[0] or 0), documents_indexed=int(counts[1] or 0), documents_failed=int(counts[2] or 0),
            api={k: stats.get(k) for k in ("requests", "retries", "errors", "rate_limited") if k in stats},
            rate_limit_used_percent=health.get("rate_limit_used_percent"), warnings=warnings,
        ),
    )


@router.get("/{source_id}/permissions", response_model=ApiResponse[SourcePermissionsSchema], summary="How this source's permissions are applied, and what is not mapped yet")
async def source_permissions(source_id: UUID, request: Request, container: ApplicationContainer = Depends(get_scoped_container)):
    tenant_id, _ = _ids(request)
    session = container.database.session()
    source = await _get_source(session, tenant_id, source_id)
    common, _ = split_config(source.configuration or {})
    connector_class = _registry.get(source.type)

    restricted = (await session.execute(select(func.count()).select_from(Document).where(Document.tenant_id == tenant_id, Document.source_id == source_id, Document.is_current.is_(True), Document.visibility == "restricted"))).scalar_one()
    mapped = select(IdentityMapping.external_id).where(IdentityMapping.tenant_id == tenant_id, IdentityMapping.provider == source.type)
    unmapped = (
        await session.execute(
            select(DocumentAccessRule.principal_type, DocumentAccessRule.principal_id, func.count(func.distinct(DocumentAccessRule.document_id)))
            .where(DocumentAccessRule.tenant_id == tenant_id, DocumentAccessRule.source_id == source_id, DocumentAccessRule.principal_id.not_in(mapped))
            .group_by(DocumentAccessRule.principal_type, DocumentAccessRule.principal_id)
            .order_by(func.count(func.distinct(DocumentAccessRule.document_id)).desc())
            .limit(100)
        )
    ).all()
    return ApiResponse(
        message="Permissions retrieved.",
        data=SourcePermissionsSchema(
            permission_mode=common.get("permission_mode", "sync_external"), default_visibility=common.get("default_visibility", "tenant"),
            default_allowed_roles=list(common.get("default_allowed_roles") or []), supports_external_permissions=connector_class.supports_permissions,
            restricted_documents=int(restricted or 0),
            unmapped_principals=[UnmappedPrincipalSchema(principal_type=t, external_id=p, documents=int(n)) for t, p, n in unmapped],
        ),
    )


# ====================================================================== webhook
@webhook_router.post("/sources/{source_id}", status_code=status.HTTP_202_ACCEPTED, summary="Change notification from the source")
async def source_webhook(source_id: UUID, request: Request, background_tasks: BackgroundTasks, container: ApplicationContainer = Depends(get_scoped_container)):
    """
    Authenticated by the per-source secret (`X-Webhook-Secret`, or `clientState` for Microsoft Graph), not by a user
    token: the caller is the external system. Body (all optional): `{"external_ids": [...]}` refreshes just those items
    (Confluence's `{"page": {"id": ...}}` is understood too); anything else queues a normal incremental sync. A burst is
    collapsed: while a sync runs, named items wait and are applied right after it. The same "404" answers "no such
    source", "webhooks off", "paused" and "wrong secret".
    """
    raw = await request.body()
    try:
        body = json.loads(raw[:65536]) if raw else {}
    except ValueError:
        body = {}
    session = container.database.session()
    source = await session.get(KnowledgeSource, source_id)

    # Microsoft Graph proves it owns the endpoint by sending a token to echo back when a subscription is created.
    token = webhooks.safe_validation_token(request.query_params.get("validationToken"))
    if token and source is not None and not source.is_deleted and source.webhook_secret_hash:
        return PlainTextResponse(token, status_code=200)

    if source is None or source.is_deleted or source.status != "active" or not webhooks.authenticated(source.webhook_secret_hash, request.headers.get("x-webhook-secret"), body):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    tenant_id, source_type = source.tenant_id, source.type
    await session.commit()

    ids = webhooks.extract_external_ids(source_type, body)
    try:
        run_id = await create_run(container, source_id, tenant_id, trigger="webhook", actor_id=None, targets=ids or None)
    except SyncAlreadyRunning:
        if ids:
            waiting = await add_pending_targets(container, source_id, tenant_id, ids)
            return {"status": "queued_after_current_sync", "waiting": waiting}
        return {"status": "already_running"}
    await dispatch(container, background_tasks, source_id, run_id)
    return {"status": "queued", "sync_id": str(run_id), "items": len(ids) or None}
