"""
The generic synchronisation engine.

    Sync job -> connector -> discover (or changes) -> per document: skip unchanged / fetch -> ingest ->
    permissions -> record  ->  removed items archived  ->  sync result

The engine is the only place that knows how a source and the ingestion pipeline meet; connectors know nothing
about chunking or embedding, and the pipeline knows nothing about connectors: it receives an IngestionRequest.

Guarantees
* Unchanged content is never re-fetched-then-embedded: version/etag/hash comparison decides (and conditional
  requests avoid the download where the source supports them).
* One document failing never stops the sync; it is recorded, retried on the next sync, and quarantined after
  MAX_DOC_FAILURES identical failures until the item changes.
* Work is bounded: at most `connector_sync_concurrency` documents are in flight, each in its own transaction.
* Removed items are archived (excluded from retrieval, kept for audit and version history), never hard-deleted,
  and a sync that would remove most of a large source is held back unless the administrator allowed it.
* A sync can be cancelled between documents, and a crashed one is reaped by the scheduler.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select

from packages.api.dependencies import request_scoped_session
from packages.config.loader import settings
from packages.connectors.access import (
    apply_access,
    default_access,
    derive_access,
    permissions_hash,
    replace_rules,
)
from packages.connectors.base import BaseKnowledgeConnector
from packages.connectors.common import split_config
from packages.connectors.credential_service import SourceCredentialService
from packages.connectors.credentials import CredentialConfigurationError, CredentialDecryptionError
from packages.connectors.http import AuthenticationFailed, ConnectorHttpError
from packages.connectors.models import (
    DiscoveryContext,
    ExternalDocument,
    ExternalDocumentContent,
    ExternalPermission,
    KnownDocument,
)
from packages.connectors.registry import ConnectorRegistry, default_registry
from packages.conversation.bootstrap import ensure_default_model_profile
from packages.domain.enums.document_status import DocumentStatus
from packages.domain.models.document import Document
from packages.domain.models.knowledge_source import ExternalDocumentRecord, KnowledgeSource, SourceSyncRun
from packages.infrastructure.container import ApplicationContainer
from packages.knowledge.bootstrap import ensure_default_knowledge_base
from packages.knowledge.loaders.factory import LoaderFactory
from packages.knowledge.schemas import IngestionRequest
from packages.shared.logging import get_logger

logger = get_logger(__name__)

MAX_DOC_FAILURES = 5
PROGRESS_FLUSH_EVERY = 10
STALE_RUN_MINUTES = 20
_SECRET_PATTERNS = re.compile(r"(?i)(bearer\s+[\w.\-~+/=]+|authorization[:=]\s*\S+|(?:token|secret|password|api[_-]?key)=\S+)")
_KEEP_METADATA = 40


def redact(text: str, limit: int = 400) -> str:
    return _SECRET_PATTERNS.sub("[redacted]", text)[:limit]


def slim_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Small, JSON-safe provenance facts only: no bulky lists (links, headings), no long text, no secrets."""
    out: dict[str, Any] = {}
    for key, value in metadata.items():
        if key in ("links", "headings", "download") or len(out) >= _KEEP_METADATA:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            out[key] = value[:300] if isinstance(value, str) else value
        elif isinstance(value, list) and len(value) <= 20 and all(isinstance(v, (str, int, float)) for v in value):
            out[key] = [v[:120] if isinstance(v, str) else v for v in value]
    return out


@dataclass
class Counters:
    discovered: int = 0
    created: int = 0
    updated: int = 0
    deleted: int = 0
    skipped: int = 0
    failed: int = 0
    permissions_updated: int = 0
    renamed: int = 0
    quarantined: int = 0
    unmapped_principals: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    indexed_sample: list[str] = field(default_factory=list)
    removed_sample: list[str] = field(default_factory=list)

    def add_error(self, external_id: str, title: str | None, stage: str, message: str) -> None:
        self.failed += 1
        if len(self.errors) < settings.rag.connector_max_error_details:
            self.errors.append({"external_id": external_id[:200], "title": (title or "")[:200], "stage": stage, "message": redact(message)})


@dataclass
class SourceSnapshot:
    """Plain copy of what the sync needs, so no ORM object crosses a session boundary."""

    id: UUID
    tenant_id: UUID
    type: str
    name: str
    knowledge_base_id: UUID | None
    common: dict[str, Any]
    specific: dict[str, Any]
    sync_state: dict[str, Any]
    sync_mode: str
    sync_interval_minutes: int | None
    previous_status: str
    targets: list[str] | None = None


class SyncEngine:
    def __init__(
        self,
        container: ApplicationContainer,
        registry: ConnectorRegistry | None = None,
        credentials: SourceCredentialService | None = None,
    ) -> None:
        self._container = container
        self._registry = registry or default_registry()
        self._credentials = credentials or SourceCredentialService()

    # ================================================================== public

    async def run(self, source_id: UUID, run_id: UUID, *, _depth: int = 0) -> str:
        """Runs one queued sync to completion. Idempotent: a run that is not `queued` is left alone."""
        started = time.monotonic()
        snapshot = await self._begin(source_id, run_id)
        if snapshot is None:
            return "skipped"

        counters = Counters()
        status, summary = "failed", None
        connector: BaseKnowledgeConnector | None = None
        new_state = dict(snapshot.sync_state)
        auth_failed = False
        held_back: str | None = None
        try:
            connector = await self._build_connector(snapshot)
            validation = await connector.validate_config()
            if not validation.ok:
                raise ValueError("Invalid configuration: " + "; ".join(validation.errors))

            await self._audit(snapshot, "source.sync_started", run_id, {"run_id": str(run_id)})
            new_state, held_back = await self._sync(snapshot, run_id, connector, counters)
            cancelled = await self._is_cancelled(run_id, fresh=True)
            if cancelled:
                status = "cancelled"
            elif counters.failed or held_back:
                status = "partial"
            else:
                status = "succeeded"
        except AuthenticationFailed as exc:
            auth_failed = True
            summary = redact(str(exc))
        except (CredentialConfigurationError, CredentialDecryptionError) as exc:
            auth_failed = True
            summary = redact(str(exc))
        except Exception as exc:  # noqa: BLE001 - a connector failure must never escape the job
            summary = redact(f"{type(exc).__name__}: {exc}")
            logger.warning("Source sync failed", sync_id=str(run_id), source_id=str(source_id), error=summary)
        finally:
            health = connector.health_stats() if connector is not None else {}
            if connector is not None:
                await connector.aclose()

        if held_back and summary is None:
            summary = held_back
        elif status == "partial" and summary is None:
            summary = f"{counters.failed} document(s) failed."
        await self._finish(snapshot, run_id, status, summary, counters, new_state, health, time.monotonic() - started, auth_failed)
        if status in ("succeeded", "partial") and _depth < 5:
            await self._drain_pending(snapshot, _depth)
        return status

    async def _drain_pending(self, snapshot: SourceSnapshot, depth: int) -> None:
        """Change notifications that arrived during this sync are applied now, as one targeted run."""
        from packages.connectors.scheduling import SyncAlreadyRunning, create_run, take_pending_targets

        ids = await take_pending_targets(self._container, snapshot.id)
        if not ids:
            return
        try:
            run_id = await create_run(self._container, snapshot.id, snapshot.tenant_id, trigger="webhook", actor_id=None, targets=ids)
        except SyncAlreadyRunning:
            from packages.connectors.scheduling import add_pending_targets

            await add_pending_targets(self._container, snapshot.id, snapshot.tenant_id, ids)  # someone else is running: try later
            return
        await self.run(snapshot.id, run_id, _depth=depth + 1)

    # ================================================================== phases

    async def _begin(self, source_id: UUID, run_id: UUID) -> SourceSnapshot | None:
        async with request_scoped_session(self._container) as session:
            run = await session.get(SourceSyncRun, run_id)
            source = await session.get(KnowledgeSource, source_id)
            if run is None or source is None or run.source_id != source.id or run.tenant_id != source.tenant_id:
                return None
            if run.status != "queued":
                return None  # already running/finished: a duplicate delivery of the job
            run.status = "running"
            run.started_at = datetime.now(UTC)
            source.last_sync_at = run.started_at
            # Resolved once here, before documents are processed in parallel: two workers racing to create the
            # default knowledge base / model profile would otherwise create duplicates.
            if source.knowledge_base_id is None:
                source.knowledge_base_id = (await ensure_default_knowledge_base(source.tenant_id, self._container.repositories.knowledge_base())).id
            await ensure_default_model_profile(self._container.repositories.model_profile())
            common, specific = split_config(source.configuration or {})
            return SourceSnapshot(
                id=source.id, tenant_id=source.tenant_id, type=source.type, name=source.name,
                knowledge_base_id=source.knowledge_base_id, common=common, specific=specific,
                sync_state=dict(source.sync_state or {}), sync_mode=source.sync_mode,
                sync_interval_minutes=source.sync_interval_minutes, previous_status=source.status,
                targets=list((run.stats or {}).get("targets") or []) or None,
            )

    async def _build_connector(self, snapshot: SourceSnapshot) -> BaseKnowledgeConnector:
        connector_class = self._registry.get(snapshot.type)
        secret = None
        if connector_class.credential_kind != "none":
            async with request_scoped_session(self._container) as session:
                source = await session.get(KnowledgeSource, snapshot.id)
                secret = await self._credentials.load(session, source)
            if secret is None:
                raise AuthenticationFailed("No credentials are configured for this source (or they were revoked).")
        return connector_class(snapshot.specific, secret, allow_private=settings.rag.connector_allow_private_hosts)

    async def _sync(self, snapshot: SourceSnapshot, run_id: UUID, connector: BaseKnowledgeConnector, counters: Counters) -> tuple[dict[str, Any], str | None]:
        state = dict(snapshot.sync_state)
        cancel_cache = {"at": 0.0, "value": False}

        async def cancelled() -> bool:
            if time.monotonic() - cancel_cache["at"] > 2.0:
                cancel_cache["value"] = await self._is_cancelled(run_id)
                cancel_cache["at"] = time.monotonic()
            return cancel_cache["value"]

        async def lookup(external_id: str) -> KnownDocument | None:
            async with request_scoped_session(self._container) as session:
                record = await self._record(session, snapshot, external_id)
                return KnownDocument(record.external_version, record.content_hash, dict(record.metadata_ or {})) if record else None

        context = DiscoveryContext(source_id=snapshot.id, tenant_id=snapshot.tenant_id, sync_id=run_id, state=state, lookup=lookup, cancelled=cancelled)

        if snapshot.targets:
            handled = await self._sync_targets(snapshot, run_id, connector, counters)
            if handled is not None:
                return handled
            snapshot.targets = None  # the connector cannot fetch single items: do a normal sync instead

        changes = await connector.get_changes(context) if connector.supports_changes and state else None
        semaphore = asyncio.Semaphore(settings.rag.connector_sync_concurrency)
        pending: set[asyncio.Task] = set()
        flushed = {"n": 0}

        async def guarded(document: ExternalDocument) -> None:
            async with semaphore:
                await self._process_one(snapshot, run_id, connector, document, counters)
            flushed["n"] += 1
            if flushed["n"] % PROGRESS_FLUSH_EVERY == 0:
                await self._flush_progress(run_id, counters)

        async def submit(document: ExternalDocument) -> None:
            counters.discovered += 1
            task = asyncio.create_task(guarded(document))
            pending.add(task)
            task.add_done_callback(pending.discard)
            if len(pending) >= settings.rag.connector_sync_concurrency * 2:
                await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)

        discovery_complete = False
        try:
            if changes is not None:
                for change in changes:
                    if await cancelled():
                        break
                    if change.kind == "deleted":
                        counters.discovered += 1
                        await self._archive_by_external_id(snapshot, run_id, change.external_id, counters)
                    elif change.document is not None:
                        await submit(change.document)
                discovery_complete = not await self._is_cancelled(run_id)
            else:
                async for document in connector.discover(context):
                    await submit(document)
                    if await cancelled():
                        break
                # Fresh read (not the 2 s cache): a cancel must never be followed by the removal sweep.
                discovery_complete = not await self._is_cancelled(run_id)
        finally:
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

        held_back = None
        if discovery_complete and changes is None:
            held_back = await self._sweep_removed(snapshot, run_id, counters, connector)

        # Delta tokens etc. advance only when everything succeeded, so a failed item is replayed next time.
        keep_new_state = discovery_complete and not counters.failed
        return (context.state if keep_new_state else dict(snapshot.sync_state)), held_back

    async def _sync_targets(self, snapshot: SourceSnapshot, run_id: UUID, connector: BaseKnowledgeConnector, counters: Counters) -> tuple[dict[str, Any], str | None] | None:
        """
        Refreshes just the items a change notification named. Items the source no longer has are archived. Returns
        None when the connector cannot fetch one item by id (the caller then runs a full sync). The sync cursor and
        the removal sweep are untouched: this is a shortcut, not a replacement for full syncs.
        """
        semaphore = asyncio.Semaphore(settings.rag.connector_sync_concurrency)

        async def one(external_id: str) -> None:
            async with semaphore:
                try:
                    document = await connector.get_external_document(external_id)
                except NotImplementedError:
                    raise
                except Exception as exc:  # noqa: BLE001 - one bad id must not stop the others
                    counters.add_error(external_id, None, "lookup", f"{type(exc).__name__}: {exc}")
                    return
                counters.discovered += 1
                if document is None:
                    await self._archive_by_external_id(snapshot, run_id, external_id, counters)
                else:
                    await self._process_one(snapshot, run_id, connector, document, counters)

        ids = list(snapshot.targets or [])
        try:
            await one(ids[0])
        except NotImplementedError:
            return None
        remaining = ids[1:]
        results = await asyncio.gather(*(one(i) for i in remaining), return_exceptions=True)
        for result in results:
            if isinstance(result, NotImplementedError):
                return None
        return dict(snapshot.sync_state), None

    # ------------------------------------------------------------------ one document

    async def _process_one(self, snapshot: SourceSnapshot, run_id: UUID, connector: BaseKnowledgeConnector, external: ExternalDocument, counters: Counters) -> None:
        stage = "lookup"
        try:
            async with request_scoped_session(self._container) as session:
                record = await self._record(session, snapshot, external.external_id)
                now = datetime.now(UTC)

                same_version = bool(
                    record and record.document_id and record.status in ("indexed", "updated")
                    and external.external_version and record.external_version == external.external_version
                )
                if (external.unchanged and record and record.document_id and record.status in ("indexed", "updated")) or same_version:
                    await self._touch(session, snapshot, run_id, record, external, now, counters)
                    await self._sync_permissions(session, snapshot, connector, external, record, counters)
                    counters.skipped += 1
                    return

                if record and record.status == "failed" and record.failure_count >= MAX_DOC_FAILURES and record.external_version == external.external_version:
                    record.last_seen_sync_id, record.last_synced_at = run_id, now
                    counters.skipped += 1
                    counters.quarantined += 1
                    return

                stage = "fetch"
                content = external.prefetched or await connector.fetch(external)

                if record and record.document_id and record.content_hash == content.content_hash and record.status != "failed":
                    restored = await self._touch(session, snapshot, run_id, record, external, now, counters, restore=True)
                    record.external_version = external.external_version
                    await self._sync_permissions(session, snapshot, connector, external, record, counters)
                    if restored:
                        counters.updated += 1
                    else:
                        counters.skipped += 1
                    return

                stage = "permissions"
                permissions = await self._permissions(connector, snapshot, external)
                access = await self._access(session, snapshot, permissions)
                counters.unmapped_principals += len(access.unmapped)

                stage = "ingest"
                document = await self._ingest(session, snapshot, run_id, external, content, access)

                is_new = record is None or record.document_id is None
                if record is None:
                    record = ExternalDocumentRecord(tenant_id=snapshot.tenant_id, source_id=snapshot.id, external_id=external.external_id)
                    session.add(record)
                self._fill_record(record, external, content, run_id, now)
                record.document_id = document.id
                record.status = "indexed" if is_new else "updated"
                record.failure_count, record.last_error = 0, None
                record.last_indexed_at = now
                record.permissions_hash = permissions_hash(permissions)
                if permissions is not None:
                    await replace_rules(session, tenant_id=snapshot.tenant_id, source_id=snapshot.id, document_id=document.id, permissions=permissions)
                    counters.permissions_updated += 1

                if is_new:
                    counters.created += 1
                else:
                    counters.updated += 1
                if len(counters.indexed_sample) < 20:
                    counters.indexed_sample.append(str(document.id))
        except Exception as exc:  # noqa: BLE001 - recorded, never raised: other documents must still sync
            counters.add_error(external.external_id, external.title, stage, f"{type(exc).__name__}: {exc}")
            await self._record_failure(snapshot, run_id, external, stage, exc)

    async def _ingest(self, session, snapshot: SourceSnapshot, run_id: UUID, external: ExternalDocument, content: ExternalDocumentContent, access) -> Document:
        suffix, payload = self._materialise(external, content)
        settings.storage.temp_directory.mkdir(parents=True, exist_ok=True)
        scratch = settings.storage.temp_directory / f"src_{uuid4().hex}{suffix}"
        scratch.write_bytes(payload)
        try:
            knowledge_base_id = snapshot.knowledge_base_id
            profile = await ensure_default_model_profile(self._container.repositories.model_profile())
            provenance = slim_metadata({**external.metadata, "source_name": snapshot.name})
            request = IngestionRequest(
                tenant_id=snapshot.tenant_id,
                model_profile_id=profile.id,
                knowledge_base_id=knowledge_base_id,
                file=scratch,
                file_id="ext:" + hashlib.sha1(f"{snapshot.id}:{external.external_id}".encode()).hexdigest(),
                document_name=(external.title or external.external_id)[:255],
                chunking_strategy=snapshot.common.get("chunking_strategy") or "recursive",
                visibility=access.visibility,
                allowed_roles=access.allowed_roles or None,
                allowed_users=access.allowed_users or None,
                source_id=snapshot.id,
                source_type=snapshot.type,
                external_id=external.external_id,
                canonical_url=external.canonical_url,
                external_version=external.external_version,
                external_updated_at=external.updated_at,
                sync_id=run_id,
                metadata=provenance,
                source_metadata=provenance,
            )
            response = await self._container.rag.ingestion_pipeline().ingest(request)
            document = await session.get(Document, response.document_id)
            if document is None:
                raise RuntimeError("Ingestion returned no document.")
            return document
        finally:
            scratch.unlink(missing_ok=True)

    @staticmethod
    def _materialise(external: ExternalDocument, content: ExternalDocumentContent) -> tuple[str, bytes]:
        if content.data is not None:
            extension = Path(content.file_name or external.title or "").suffix.lower()
            if extension not in LoaderFactory.supported_extensions():
                raise ValueError(f"Unsupported file type '{extension or 'none'}'.")
            return extension, content.data
        text = content.text or ""
        if not text.strip():
            raise ValueError("The item has no readable text.")
        markdown = (content.mime_type or "").endswith("markdown") or text.lstrip().startswith("#")
        return (".md" if markdown else ".txt"), text.encode("utf-8")

    # ------------------------------------------------------------------ permissions

    async def _permissions(self, connector: BaseKnowledgeConnector, snapshot: SourceSnapshot, external: ExternalDocument) -> list[ExternalPermission] | None:
        if not connector.supports_permissions or snapshot.common.get("permission_mode", "sync_external") != "sync_external":
            return None
        try:
            return external.permissions if external.permissions is not None else await connector.get_permissions(external)
        except ConnectorHttpError as exc:
            if isinstance(exc, AuthenticationFailed):
                raise
            logger.warning("Could not read permissions", external_id=external.external_id, error=redact(str(exc)))
            return None

    async def _access(self, session, snapshot: SourceSnapshot, permissions: list[ExternalPermission] | None):
        rules = None if permissions is None else [(p.principal_type, p.principal_id, p.permission) for p in permissions]
        return await derive_access(session, tenant_id=snapshot.tenant_id, provider=snapshot.type, rules=rules, configuration=snapshot.common)

    async def _sync_permissions(self, session, snapshot: SourceSnapshot, connector: BaseKnowledgeConnector, external: ExternalDocument, record: ExternalDocumentRecord, counters: Counters) -> None:
        """Permission changes without a content change: update the ACL only, no re-embedding."""
        if not record.document_id:
            return
        permissions = await self._permissions(connector, snapshot, external)
        if permissions_hash(permissions) == record.permissions_hash:
            return
        document = await session.get(Document, record.document_id)
        if document is None:
            return
        access = await self._access(session, snapshot, permissions)
        apply_access(document, access)
        if permissions is not None:
            await replace_rules(session, tenant_id=snapshot.tenant_id, source_id=snapshot.id, document_id=document.id, permissions=permissions)
        record.permissions_hash = permissions_hash(permissions)
        counters.permissions_updated += 1
        counters.unmapped_principals += len(access.unmapped)

    # ------------------------------------------------------------------ records

    async def _record(self, session, snapshot: SourceSnapshot, external_id: str) -> ExternalDocumentRecord | None:
        return (
            await session.execute(
                select(ExternalDocumentRecord).where(
                    ExternalDocumentRecord.tenant_id == snapshot.tenant_id,
                    ExternalDocumentRecord.source_id == snapshot.id,
                    ExternalDocumentRecord.external_id == external_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    def _fill_record(record: ExternalDocumentRecord, external: ExternalDocument, content: ExternalDocumentContent | None, run_id: UUID, now: datetime) -> None:
        record.title = (external.title or "")[:1024]
        record.canonical_url = external.canonical_url
        record.parent_external_id = external.parent_external_id
        record.external_version = external.external_version
        record.external_updated_at = external.updated_at
        if content is not None:
            record.content_hash = content.content_hash
        record.last_seen_sync_id = run_id
        record.last_synced_at = now
        record.deleted_at_source = None
        record.metadata_ = slim_metadata(external.metadata) | {k: external.metadata[k] for k in ("etag", "last_modified", "links") if k in external.metadata}

    async def _touch(self, session, snapshot: SourceSnapshot, run_id: UUID, record: ExternalDocumentRecord, external: ExternalDocument, now: datetime, counters: Counters, *, restore: bool = False) -> bool:
        """Marks an unchanged item as seen, applying renames/moves and un-archiving a returned item. Returns True if restored."""
        renamed = (external.title and external.title != record.title) or (external.canonical_url and external.canonical_url != record.canonical_url) or external.parent_external_id != record.parent_external_id
        restored = record.status == "deleted"
        document = await session.get(Document, record.document_id) if record.document_id else None
        if document is not None:
            if renamed:
                document.title = (external.title or document.title)[:255]
                document.file_name = document.title
                document.canonical_url = external.canonical_url or document.canonical_url
                counters.renamed += 1
            if restored:
                document.status = DocumentStatus.READY
            document.last_synced_at = now
            document.sync_id = run_id
            if external.updated_at:
                document.external_updated_at = external.updated_at
        existing_meta = dict(record.metadata_ or {})
        self._fill_record(record, external, None, run_id, now)
        for keep in ("etag", "last_modified", "links"):
            if keep not in external.metadata and keep in existing_meta:
                record.metadata_ = {**record.metadata_, keep: existing_meta[keep]}
        if restored:
            record.status = "updated"
        return restored

    async def _record_failure(self, snapshot: SourceSnapshot, run_id: UUID, external: ExternalDocument, stage: str, exc: Exception) -> None:
        try:
            async with request_scoped_session(self._container) as session:
                record = await self._record(session, snapshot, external.external_id)
                if record is None:
                    record = ExternalDocumentRecord(tenant_id=snapshot.tenant_id, source_id=snapshot.id, external_id=external.external_id)
                    session.add(record)
                    record.title = (external.title or "")[:1024]
                    record.canonical_url = external.canonical_url
                record.external_version = external.external_version
                record.status = "failed"
                record.failure_count = (record.failure_count or 0) + 1
                record.last_error = redact(f"[{stage}] {type(exc).__name__}: {exc}")
                record.last_seen_sync_id = run_id
                record.last_synced_at = datetime.now(UTC)
        except Exception as inner:  # noqa: BLE001
            logger.warning("Could not record a document failure", error=redact(str(inner)))

    # ------------------------------------------------------------------ removals

    async def _archive(self, session, snapshot: SourceSnapshot, record: ExternalDocumentRecord, counters: Counters) -> None:
        if record.document_id:
            document = await session.get(Document, record.document_id)
            if document is not None and document.status != DocumentStatus.ARCHIVED:
                document.status = DocumentStatus.ARCHIVED  # excluded from retrieval; rows, chunks and versions are kept
        record.status = "deleted"
        record.deleted_at_source = datetime.now(UTC)
        counters.deleted += 1
        if len(counters.removed_sample) < 20:
            counters.removed_sample.append(record.external_id[:120])

    async def _archive_by_external_id(self, snapshot: SourceSnapshot, run_id: UUID, external_id: str, counters: Counters) -> None:
        async with request_scoped_session(self._container) as session:
            record = await self._record(session, snapshot, external_id)
            if record is not None and record.status != "deleted":
                await self._archive(session, snapshot, record, counters)

    async def _sweep_removed(self, snapshot: SourceSnapshot, run_id: UUID, counters: Counters, connector: BaseKnowledgeConnector) -> str | None:
        """Archives items the source no longer lists. Returns a message when the sweep was held back."""
        async with request_scoped_session(self._container) as session:
            base = (ExternalDocumentRecord.tenant_id == snapshot.tenant_id, ExternalDocumentRecord.source_id == snapshot.id, ExternalDocumentRecord.status != "deleted")
            known = (await session.execute(select(func.count()).select_from(ExternalDocumentRecord).where(*base))).scalar_one()
            unseen_ids = list(
                (await session.execute(select(ExternalDocumentRecord.id).where(*base, (ExternalDocumentRecord.last_seen_sync_id.is_(None)) | (ExternalDocumentRecord.last_seen_sync_id != run_id)))).scalars()
            )
            if not unseen_ids:
                return None
            if counters.discovered == 0 and known > 0:
                return "The source returned no items; nothing was removed (a listing failure would otherwise archive everything)."
            if known >= 20 and len(unseen_ids) / known > 0.5 and not snapshot.common.get("allow_bulk_delete"):
                return f"{len(unseen_ids)} of {known} documents disappeared from the source; removals were held back. Enable 'Allow removing most documents' if this is expected."
            for record_id in unseen_ids:
                record = await session.get(ExternalDocumentRecord, record_id)
                if record is not None and record.status != "deleted":
                    await self._archive(session, snapshot, record, counters)
        return None

    # ------------------------------------------------------------------ bookkeeping

    async def _is_cancelled(self, run_id: UUID, *, fresh: bool = False) -> bool:
        async with request_scoped_session(self._container) as session:
            run = await session.get(SourceSyncRun, run_id)
            return bool(run and run.cancel_requested)

    async def _flush_progress(self, run_id: UUID, counters: Counters) -> None:
        try:
            async with request_scoped_session(self._container) as session:
                run = await session.get(SourceSyncRun, run_id)
                if run is not None:
                    self._copy_counters(run, counters)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not flush sync progress", error=redact(str(exc)))

    @staticmethod
    def _copy_counters(run: SourceSyncRun, c: Counters) -> None:
        run.documents_discovered, run.documents_created, run.documents_updated = c.discovered, c.created, c.updated
        run.documents_deleted, run.documents_skipped, run.documents_failed = c.deleted, c.skipped, c.failed
        run.permissions_updated, run.error_count = c.permissions_updated, c.failed
        run.errors = list(c.errors)

    async def _finish(self, snapshot: SourceSnapshot, run_id: UUID, status: str, summary: str | None, c: Counters, state: dict[str, Any], health: dict[str, Any], seconds: float, auth_failed: bool) -> None:
        now = datetime.now(UTC)
        async with request_scoped_session(self._container) as session:
            run = await session.get(SourceSyncRun, run_id)
            source = await session.get(KnowledgeSource, snapshot.id)
            if run is not None:
                self._copy_counters(run, c)
                run.status, run.completed_at, run.error_summary = status, now, summary
                run.stats = {**(run.stats or {}), "duration_seconds": round(seconds, 2), "renamed": c.renamed, "quarantined": c.quarantined, "unmapped_principals": c.unmapped_principals, **{k: v for k, v in health.items() if k in ("requests", "retries", "errors", "rate_limited", "crawl")}}
            if source is not None:
                source.last_sync_status = status
                if status in ("succeeded", "partial"):
                    source.last_successful_sync_at = now
                    # Keep notifications that arrived while this ran (they live in sync_state too).
                    source.sync_state = {**state, "pending_targets": (source.sync_state or {}).get("pending_targets", [])}
                    if source.status in ("error", "disconnected"):
                        source.status = "active"
                elif status == "failed":
                    source.status = "disconnected" if auth_failed else "error"
                source.health = {
                    **health,
                    "connection": "disconnected" if auth_failed else ("error" if status == "failed" else "healthy"),
                    "authentication": "invalid" if auth_failed else "valid",
                    "last_sync_seconds": round(seconds, 2),
                    "last_sync_status": status,
                    "checked_at": now.isoformat(),
                }
                if source.sync_mode == "scheduled" and source.sync_interval_minutes and source.status == "active" and not snapshot.targets:
                    source.next_sync_at = now + timedelta(minutes=source.sync_interval_minutes)

        action = {"succeeded": "source.sync_completed", "partial": "source.sync_completed", "cancelled": "source.sync_stopped"}.get(status, "source.sync_failed")
        await self._audit(snapshot, action, run_id, {"status": status, "created": c.created, "updated": c.updated, "deleted": c.deleted, "skipped": c.skipped, "failed": c.failed, "error": summary})
        if c.indexed_sample:
            await self._audit(snapshot, "source.documents_indexed", run_id, {"count": c.created + c.updated, "sample_document_ids": c.indexed_sample})
        if c.removed_sample:
            await self._audit(snapshot, "source.documents_removed", run_id, {"count": c.deleted, "sample": c.removed_sample})

    async def _audit(self, snapshot: SourceSnapshot, action: str, run_id: UUID, detail: dict[str, Any]) -> None:
        await self._container.audit().record(
            tenant_id=snapshot.tenant_id, action=action, resource_type="knowledge_source", resource_id=snapshot.id,
            detail={"source_name": snapshot.name, "source_type": snapshot.type, "sync_id": str(run_id), **detail},
        )
