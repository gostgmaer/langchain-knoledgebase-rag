# Knowledge source models
"""
External knowledge sources and everything a sync leaves behind.

    KnowledgeSource 1-n SourceSyncRun          (one row per sync: counters, status, errors)
    KnowledgeSource 1-n ExternalDocumentRecord (what the source has, and which internal Document it became)
    KnowledgeSource 1-1 SourceCredential       (encrypted secret; never returned by any API)
    Document.source_id / external_id           (provenance back to the external record)
    DocumentAccessRule                         (normalised external ACL, kept for audit and re-mapping)
    IdentityMapping                            (external user/group -> internal user/role)

Statuses are plain strings validated in code (see the *_STATUSES tuples) so adding one never needs a
database enum migration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.domain.models.base import BaseModel

SOURCE_STATUSES = ("active", "paused", "error", "disconnected")
SYNC_MODES = ("manual", "scheduled", "webhook", "realtime")
SYNC_RUN_STATUSES = ("queued", "running", "succeeded", "partial", "failed", "cancelled")
EXTERNAL_DOC_STATUSES = ("discovered", "pending", "fetching", "processing", "indexed", "updated", "deleted", "failed")


class KnowledgeSource(BaseModel):
    """One configured connection to an external knowledge system, owned by exactly one tenant."""

    __tablename__ = "knowledge_sources"

    __table_args__ = (
        Index("ix_source_tenant", "tenant_id"),
        Index("ix_source_due", "status", "sync_mode", "next_sync_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    knowledge_base_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="paused")
    sync_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    sync_interval_minutes: Mapped[int | None] = mapped_column(Integer)

    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_status: Mapped[str | None] = mapped_column(String(16))

    # Connector-specific settings (content selection, filters, permission behaviour). NEVER secrets.
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # Opaque per-source state a connector keeps between syncs (delta links, watermarks).
    sync_state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # Last known health snapshot (connection/auth status, request and error counts, rate-limit info).
    health: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # SHA-256 of the webhook secret (the secret itself is shown once, on creation/rotation).
    webhook_secret_hash: Mapped[str | None] = mapped_column(String(64))

    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))


class SourceCredential(BaseModel):
    """
    Encrypted credential for one source. `ciphertext` is a Fernet token; the plaintext never touches
    a normal column, a log line or an API response. Scoped by (tenant_id, source_id) and re-checked
    on every read.
    """

    __tablename__ = "source_credentials"

    __table_args__ = (Index("uq_source_credential_source", "source_id", unique=True),)

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    """basic | token | oauth_client | none - describes the shape, never the value."""
    ciphertext: Mapped[str | None] = mapped_column(Text)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))


class SourceSyncRun(BaseModel):
    """One synchronisation of one source. `id` is the syncId used in logs, audit and provenance."""

    __tablename__ = "source_sync_runs"

    __table_args__ = (Index("ix_sync_source_started", "source_id", "started_at"),)

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False
    )
    trigger: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    """manual | schedule | webhook | resume"""
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    triggered_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    trace_id: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64))

    documents_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    documents_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    documents_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    documents_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    documents_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    documents_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    permissions_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    error_summary: Mapped[str | None] = mapped_column(Text)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    """Bounded list of {external_id, title, stage, message} for the failures of this run."""
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ExternalDocumentRecord(BaseModel):
    """
    What a source holds, keyed by (source_id, external_id). Change detection compares
    `external_version` / `content_hash` here, so an unchanged item is never fetched or embedded again.
    `document_id` is the current internal Document; older versions stay reachable through
    document_versions.
    """

    __tablename__ = "external_documents"

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_external_document"),
        Index("ix_external_doc_tenant_source", "tenant_id", "source_id", "status"),
        Index("ix_external_doc_document", "document_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(1024), nullable=False)
    document_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))

    title: Mapped[str | None] = mapped_column(String(1024))
    canonical_url: Mapped[str | None] = mapped_column(Text)
    parent_external_id: Mapped[str | None] = mapped_column(String(1024))
    external_version: Mapped[str | None] = mapped_column(String(256))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    permissions_hash: Mapped[str | None] = mapped_column(String(64))
    external_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="discovered")
    last_seen_sync_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at_source: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class DocumentAccessRule(BaseModel):
    """A normalised permission from the external system. Kept so ACLs can be re-derived when identity mappings change."""

    __tablename__ = "document_access_rules"

    __table_args__ = (
        Index("ix_access_rule_document", "document_id"),
        Index("ix_access_rule_tenant_source", "tenant_id", "source_id"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    principal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    """user | group | role"""
    principal_id: Mapped[str] = mapped_column(String(512), nullable=False)
    permission: Mapped[str] = mapped_column(String(16), nullable=False, default="read")


class IdentityMapping(BaseModel):
    """
    Maps an external principal (a Confluence account, a Microsoft group, ...) to an internal one.
    External ids are never assumed to equal internal ids: an unmapped principal grants nothing.
    """

    __tablename__ = "identity_mappings"

    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", "principal_type", "external_id", name="uq_identity_mapping"),
        Index("ix_identity_tenant_provider", "tenant_id", "provider"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    """Source type the identity comes from: confluence, microsoft_teams, sharepoint, ..."""
    principal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    """user | group"""
    external_id: Mapped[str] = mapped_column(String(512), nullable=False)
    internal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    """user (an IAM user id) | role (an IAM role name)"""
    internal_id: Mapped[str] = mapped_column(String(256), nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
