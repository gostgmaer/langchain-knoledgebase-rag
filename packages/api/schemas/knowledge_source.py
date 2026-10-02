"""API schemas for knowledge sources. No schema here ever carries a credential value."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SyncMode = Literal["manual", "scheduled", "webhook", "realtime"]
ALLOWED_INTERVALS = (15, 30, 60, 1440, 10080)  # 15 min, 30 min, hourly, daily, weekly


class CredentialStatusSchema(BaseModel):
    configured: bool
    kind: str | None = None
    revoked: bool = False
    updated_at: datetime | None = None


class SourceCreateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    type: str
    description: str | None = Field(default=None, max_length=2000)
    configuration: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, Any] | None = Field(
        default=None,
        description="Write-only. Encrypted at rest and never returned by any endpoint.",
    )
    sync_mode: SyncMode = "manual"
    sync_interval_minutes: int | None = None
    knowledge_base_id: UUID | None = None


class SourceUpdateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    configuration: dict[str, Any] | None = None
    sync_mode: SyncMode | None = None
    sync_interval_minutes: int | None = None


class CredentialsSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credentials: dict[str, Any] = Field(description="Write-only. Replaces any existing credential (rotation).")


class TestConnectionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    configuration: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, Any] | None = None


class SyncRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activate: bool = Field(default=False, description="Also activate a paused source (the wizard's final step).")


class SourceResponseSchema(BaseModel):
    id: UUID
    name: str
    type: str
    type_label: str
    description: str | None
    status: str
    sync_mode: str
    sync_interval_minutes: int | None
    last_sync_at: datetime | None
    next_sync_at: datetime | None
    last_successful_sync_at: datetime | None
    last_sync_status: str | None
    configuration: dict[str, Any]
    knowledge_base_id: UUID | None
    credential: CredentialStatusSchema
    document_count: int = 0
    failed_count: int = 0
    health: dict[str, Any] = {}
    webhook_enabled: bool = False
    webhook_secret: str | None = None
    """Shown once, when it is created or rotated."""
    created_at: datetime
    updated_at: datetime


class SourceListSchema(BaseModel):
    total: int
    sources: list[SourceResponseSchema]


class ConnectorTypeSchema(BaseModel):
    type: str
    display_name: str
    description: str
    icon: str
    available: bool
    credential_kind: str
    credential_fields: list[dict[str, Any]]
    config_schema: list[dict[str, Any]]
    supports_permissions: bool
    supports_changes: bool
    notes: str | None


class ConnectorTypesSchema(BaseModel):
    types: list[ConnectorTypeSchema]
    common_fields: list[dict[str, Any]]
    sync_intervals: list[dict[str, Any]]


class ValidationSchema(BaseModel):
    ok: bool
    errors: list[str] = []
    warnings: list[str] = []


class ConnectionTestSchema(BaseModel):
    ok: bool
    message: str
    authenticated: bool | None = None
    details: dict[str, Any] = {}
    validation: ValidationSchema | None = None


class PreviewItemSchema(BaseModel):
    external_id: str
    title: str
    url: str | None
    version: str | None
    updated_at: datetime | None
    metadata: dict[str, Any] = {}


class PreviewSchema(BaseModel):
    items: list[PreviewItemSchema]
    truncated: bool
    warnings: list[str] = []


class SyncRunSchema(BaseModel):
    id: UUID
    source_id: UUID
    trigger: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: float | None
    documents_discovered: int
    documents_created: int
    documents_updated: int
    documents_deleted: int
    documents_skipped: int
    documents_failed: int
    permissions_updated: int
    error_count: int
    error_summary: str | None
    trace_id: str | None
    request_id: str | None
    stats: dict[str, Any] = {}


class SyncRunDetailSchema(SyncRunSchema):
    errors: list[dict[str, Any]] = []


class SyncRunListSchema(BaseModel):
    total: int
    limit: int
    offset: int
    runs: list[SyncRunSchema]


class ExternalDocumentSchema(BaseModel):
    id: UUID
    external_id: str
    title: str | None
    canonical_url: str | None
    status: str
    document_id: UUID | None
    external_version: str | None
    external_updated_at: datetime | None
    last_synced_at: datetime | None
    last_indexed_at: datetime | None
    freshness_seconds: int | None
    """Seconds between the source's last change and our last indexing (None if either is unknown)."""
    failure_count: int
    last_error: str | None
    metadata: dict[str, Any] = {}


class ExternalDocumentListSchema(BaseModel):
    total: int
    limit: int
    offset: int
    documents: list[ExternalDocumentSchema]


class SourceHealthSchema(BaseModel):
    connection: str
    authentication: str
    last_successful_sync_at: datetime | None
    last_failed_sync_at: datetime | None
    last_failure: str | None
    avg_sync_seconds: float | None
    documents_discovered: int
    documents_indexed: int
    documents_failed: int
    api: dict[str, Any] = {}
    rate_limit_used_percent: int | None = None
    warnings: list[str] = []


class SourcesSummarySchema(BaseModel):
    total_sources: int
    connected_sources: int
    disconnected_sources: int
    sources_with_errors: int
    paused_sources: int
    total_documents: int
    total_chunks: int
    documents_added_today: int
    documents_updated_today: int
    documents_deleted_today: int
    failed_documents: int
    last_sync_duration_seconds: float | None
    stale_documents: int


class IdentityMappingSchema(BaseModel):
    id: UUID | None = None
    provider: str
    principal_type: Literal["user", "group"]
    external_id: str = Field(min_length=1, max_length=512)
    internal_type: Literal["user", "role"]
    internal_id: str = Field(min_length=1, max_length=256)


class IdentityMappingListSchema(BaseModel):
    mappings: list[IdentityMappingSchema]


class UnmappedPrincipalSchema(BaseModel):
    principal_type: str
    external_id: str
    documents: int


class SourcePermissionsSchema(BaseModel):
    permission_mode: str
    default_visibility: str
    default_allowed_roles: list[str]
    supports_external_permissions: bool
    restricted_documents: int
    unmapped_principals: list[UnmappedPrincipalSchema]
