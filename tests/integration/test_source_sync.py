"""
The sync engine against real Postgres with a scripted connector and a stand-in for the ingestion pipeline (no embedding
provider needed). Uses committed rows under a fresh tenant per test, removed afterwards: the engine processes documents in
parallel on separate connections, which the single-transaction `db_session` fixture cannot express.
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from dependency_injector import providers
from sqlalchemy import delete, func, select, text

from packages.api.dependencies import request_scoped_session
from packages.connectors.base import BaseKnowledgeConnector, ConfigField
from packages.connectors.credential_service import CredentialScopeError, SourceCredentialService
from packages.connectors.credentials import CredentialCipher
from packages.connectors.http import AuthenticationFailed, ConnectorHttpError
from packages.connectors.models import (
    ConnectionTestResult,
    ExternalChange,
    ExternalDocument,
    ExternalDocumentContent,
    ExternalPermission,
)
from packages.connectors.registry import ConnectorRegistry
from packages.connectors.sync import MAX_DOC_FAILURES, SyncEngine
from packages.domain.enums.document_status import DocumentStatus
from packages.domain.models.document import Document
from packages.domain.models.knowledge_source import (
    DocumentAccessRule,
    ExternalDocumentRecord,
    IdentityMapping,
    KnowledgeSource,
    SourceCredential,
    SourceSyncRun,
)
from packages.knowledge.schemas import IngestionResponse

pytestmark = pytest.mark.integration

TEST_KEY = Fernet.generate_key().decode()


# ------------------------------------------------------------------ scripted world
class World:
    """What the fake external system currently holds, and what was asked of it."""

    def __init__(self) -> None:
        self.items: dict[str, dict] = {}
        self.fetches: list[str] = []
        self.fail_fetch: set[str] = set()
        self.discovery_error: Exception | None = None
        self.changes: list[ExternalChange] | None = None
        self.cancel_after: int | None = None
        self.state_out: dict = {}
        self.no_single = False
        self.on_discover = None

    def put(self, external_id: str, *, title: str | None = None, text: str = "body", version: str = "1", permissions=None, url: str | None = None):
        self.items[external_id] = {
            "title": title or external_id, "text": text, "version": version, "permissions": permissions,
            "url": url or f"https://source.test/{external_id}",
        }


class ScriptedConnector(BaseKnowledgeConnector):
    type = "s3"
    display_name = "Scripted"
    config_schema = (ConfigField("bucket", "Bucket"),)
    supports_permissions = True
    supports_changes = True
    world: World

    async def test_connection(self):
        return ConnectionTestResult(True, "ok")

    def _doc(self, external_id: str) -> ExternalDocument:
        item = self.world.items[external_id]
        return ExternalDocument(
            external_id=external_id, title=item["title"], canonical_url=item["url"], external_version=item["version"],
            updated_at=datetime(2026, 9, 1, tzinfo=UTC), permissions=item["permissions"], metadata={"bucket": "b"},
        )

    async def discover(self, context):
        if self.world.discovery_error is not None:
            raise self.world.discovery_error
        if self.world.on_discover is not None:
            await self.world.on_discover()
        for count, external_id in enumerate(list(self.world.items)):
            if self.world.cancel_after is not None and count == self.world.cancel_after:
                async with request_scoped_session(self.container) as session:  # the admin presses "stop"
                    run = await session.get(SourceSyncRun, context.sync_id)
                    run.cancel_requested = True
            yield self._doc(external_id)
        context.state["cursor"] = "after-full-listing"

    async def fetch(self, document):
        self.world.fetches.append(document.external_id)
        if document.external_id in self.world.fail_fetch:
            raise ConnectorHttpError("Bearer abc123SECRET timed out fetching the item")
        return ExternalDocumentContent(text=self.world.items[document.external_id]["text"], mime_type="text/plain")

    async def get_changes(self, context):
        return self.world.changes

    async def get_permissions(self, document):
        return self.world.items[document.external_id]["permissions"]

    async def get_external_document(self, external_id):
        if self.world.no_single:
            raise NotImplementedError
        return self._doc(external_id) if external_id in self.world.items else None


class FakePipeline:
    """Stands in for embedding: creates the Document row (with versioning) exactly as the real pipeline records it."""

    def __init__(self, documents) -> None:
        self.documents = documents

    async def ingest(self, request):
        checksum = hashlib.sha256(request.file.read_bytes()).hexdigest()
        previous = await self.documents.get_current_by_source_external(request.tenant_id, request.source_id, request.external_id)
        if previous is not None:
            previous.is_current = False
        document = Document(
            knowledge_base_id=request.knowledge_base_id, tenant_id=request.tenant_id, title=request.document_name,
            file_id=request.file_id, file_name=request.document_name, mime_type="text/plain", extension=request.file.suffix,
            size_bytes=1, checksum=checksum, status=DocumentStatus.READY, is_current=True, metadata_=request.metadata,
            visibility=request.visibility, allowed_roles=request.allowed_roles, allowed_users=request.allowed_users,
            source_id=request.source_id, source_type=request.source_type, external_id=request.external_id,
            canonical_url=request.canonical_url, external_version=request.external_version, sync_id=request.sync_id,
            external_updated_at=request.external_updated_at,
        )
        await self.documents.create(document)
        return IngestionResponse(document_id=document.id, chunk_count=1, embedding_count=1, superseded_document_id=previous.id if previous else None)


@pytest.fixture()
def world() -> World:
    return World()


@pytest_asyncio.fixture()
async def env(container, world) -> AsyncIterator[dict]:
    connector = type("Connector", (ScriptedConnector,), {"world": world, "container": container})
    registry = ConnectorRegistry()
    registry.register(connector)
    container.rag.ingestion_pipeline.override(providers.Factory(FakePipeline, documents=container.repositories.document))

    tenant_id = uuid4()
    async with request_scoped_session(container) as session:
        source = KnowledgeSource(tenant_id=tenant_id, name=f"scripted-{uuid4().hex[:6]}", type="s3", status="active", sync_mode="manual", configuration={"bucket": "b"})
        session.add(source)
        await session.flush()
        source_id = source.id

    engine = SyncEngine(container, registry=registry, credentials=SourceCredentialService(CredentialCipher(TEST_KEY)))

    async def sync(targets=None, **_) -> tuple[str, UUID]:
        async with request_scoped_session(container) as session:
            run = SourceSyncRun(tenant_id=tenant_id, source_id=source_id, trigger="webhook" if targets else "manual", status="queued", stats={"targets": targets} if targets else {})
            session.add(run)
            await session.flush()
            run_id = run.id
        return await engine.run(source_id, run_id), run_id

    async def run_row(run_id) -> SourceSyncRun:
        async with request_scoped_session(container) as session:
            run = await session.get(SourceSyncRun, run_id)
            session.expunge(run)
            return run

    async def docs(**filters) -> list[Document]:
        async with request_scoped_session(container) as session:
            rows = (await session.execute(select(Document).where(Document.tenant_id == tenant_id, Document.source_id == source_id).order_by(Document.created_at))).scalars().all()
            return [d for d in rows if all(getattr(d, k) == v for k, v in filters.items())]

    async def records() -> dict[str, ExternalDocumentRecord]:
        async with request_scoped_session(container) as session:
            rows = (await session.execute(select(ExternalDocumentRecord).where(ExternalDocumentRecord.source_id == source_id))).scalars().all()
            return {r.external_id: r for r in rows}

    async def edit_source(**values):
        async with request_scoped_session(container) as session:
            src = await session.get(KnowledgeSource, source_id)
            for key, value in values.items():
                setattr(src, key, value)

    async def get_source() -> KnowledgeSource:
        async with request_scoped_session(container) as session:
            src = await session.get(KnowledgeSource, source_id)
            session.expunge(src)
            return src

    yield {"tenant_id": tenant_id, "source_id": source_id, "sync": sync, "run": run_row, "docs": docs, "records": records, "edit": edit_source, "source": get_source, "container": container}

    async with request_scoped_session(container) as session:
        for model in (DocumentAccessRule, IdentityMapping, Document):
            await session.execute(delete(model).where(model.tenant_id == tenant_id))
        await session.execute(delete(KnowledgeSource).where(KnowledgeSource.tenant_id == tenant_id))
        await session.execute(text("delete from knowledge_bases where tenant_id = :t"), {"t": tenant_id})
        await session.execute(text("delete from audit_events where tenant_id = :t"), {"t": tenant_id})
    container.rag.ingestion_pipeline.reset_override()


def counts(run: SourceSyncRun) -> tuple[int, int, int, int, int, int]:
    return (run.documents_discovered, run.documents_created, run.documents_updated, run.documents_deleted, run.documents_skipped, run.documents_failed)


# ------------------------------------------------------------------ lifecycle
@pytest.mark.asyncio
async def test_first_sync_creates_documents_with_full_provenance(env, world):
    world.put("a", title="Alpha", text="alpha text")
    world.put("b", title="Beta", text="beta text")

    status, run_id = await env["sync"]()
    run = await env["run"](run_id)

    assert status == "succeeded" and counts(run) == (2, 2, 0, 0, 0, 0)
    documents = await env["docs"]()
    assert {d.title for d in documents} == {"Alpha", "Beta"}
    alpha = next(d for d in documents if d.title == "Alpha")
    assert (alpha.source_id, alpha.source_type, alpha.external_id, alpha.canonical_url) == (env["source_id"], "s3", "a", "https://source.test/a")
    assert alpha.sync_id == run_id and alpha.status == DocumentStatus.READY

    records = await env["records"]()
    assert records["a"].status == "indexed" and records["a"].document_id == alpha.id and records["a"].content_hash


@pytest.mark.asyncio
async def test_a_second_sync_of_unchanged_content_fetches_and_embeds_nothing(env, world):
    world.put("a"), world.put("b")
    await env["sync"]()
    world.fetches.clear()

    status, run_id = await env["sync"]()
    run = await env["run"](run_id)

    assert status == "succeeded" and counts(run) == (2, 0, 0, 0, 2, 0)
    assert world.fetches == []  # same external version: not even downloaded
    assert len(await env["docs"]()) == 2  # no new document versions


@pytest.mark.asyncio
async def test_a_changed_item_becomes_a_new_version_and_the_old_one_is_kept(env, world):
    world.put("a", text="v1 text", version="1")
    await env["sync"]()

    world.put("a", text="v2 text", version="2")
    status, run_id = await env["sync"]()

    assert counts(await env["run"](run_id)) == (1, 0, 1, 0, 0, 0)
    versions = await env["docs"]()
    assert [(d.external_version, d.is_current) for d in versions] == [("1", False), ("2", True)]
    assert (await env["records"]())["a"].status == "updated"


@pytest.mark.asyncio
async def test_a_new_external_version_with_identical_content_is_not_re_embedded(env, world):
    world.put("a", text="same text", version="1")
    await env["sync"]()
    world.put("a", text="same text", version="2")  # e.g. only page metadata changed at the source

    _, run_id = await env["sync"]()

    assert counts(await env["run"](run_id)) == (1, 0, 0, 0, 1, 0)
    assert len(await env["docs"]()) == 1


@pytest.mark.asyncio
async def test_a_rename_updates_the_title_without_reprocessing(env, world):
    world.put("a", title="Old name", text="text", version="1", url="https://source.test/old")
    await env["sync"]()
    world.put("a", title="New name", text="text", version="1", url="https://source.test/new")

    _, run_id = await env["sync"]()

    run = await env["run"](run_id)
    assert counts(run) == (1, 0, 0, 0, 1, 0) and run.stats["renamed"] == 1
    (document,) = await env["docs"]()
    assert (document.title, document.canonical_url) == ("New name", "https://source.test/new")


@pytest.mark.asyncio
async def test_removed_items_are_archived_not_deleted_and_can_return(env, world):
    world.put("a"), world.put("b")
    await env["sync"]()

    del world.items["b"]
    _, run_id = await env["sync"]()
    assert counts(await env["run"](run_id)) == (1, 0, 0, 1, 1, 0)
    by_id = {d.external_id: d for d in await env["docs"]()}
    assert by_id["b"].status == DocumentStatus.ARCHIVED  # excluded from retrieval, but the row is still there
    assert (await env["records"]())["b"].status == "deleted"

    world.put("b")  # the source brings it back unchanged
    _, run_id = await env["sync"]()
    assert counts(await env["run"](run_id)) == (2, 0, 1, 0, 1, 0)
    assert {d.external_id: d for d in await env["docs"]()}["b"].status == DocumentStatus.READY


# ------------------------------------------------------------------ failures
@pytest.mark.asyncio
async def test_one_failing_document_does_not_stop_the_sync_and_secrets_are_redacted(env, world):
    world.put("a"), world.put("bad"), world.put("c")
    world.fail_fetch.add("bad")

    status, run_id = await env["sync"]()
    run = await env["run"](run_id)

    assert status == "partial" and counts(run) == (3, 2, 0, 0, 0, 1)
    assert run.errors[0]["external_id"] == "bad" and run.errors[0]["stage"] == "fetch"
    assert "abc123SECRET" not in run.errors[0]["message"]
    record = (await env["records"]())["bad"]
    assert record.status == "failed" and record.failure_count == 1 and "abc123SECRET" not in record.last_error
    assert {d.external_id for d in await env["docs"]()} == {"a", "c"}


@pytest.mark.asyncio
async def test_a_failing_item_is_quarantined_until_it_changes(env, world):
    world.put("bad", version="1")
    world.fail_fetch.add("bad")
    for _ in range(MAX_DOC_FAILURES):
        await env["sync"]()
    world.fetches.clear()

    _, run_id = await env["sync"]()
    run = await env["run"](run_id)
    assert world.fetches == [] and run.stats["quarantined"] == 1  # not hammered again

    world.put("bad", version="2")  # the source changed it: worth another attempt
    world.fail_fetch.clear()
    _, run_id = await env["sync"]()
    assert counts(await env["run"](run_id)) == (1, 1, 0, 0, 0, 0)


@pytest.mark.asyncio
async def test_an_empty_listing_never_archives_everything(env, world):
    world.put("a"), world.put("b")
    await env["sync"]()
    world.items.clear()

    status, run_id = await env["sync"]()
    run = await env["run"](run_id)

    assert status == "partial" and run.documents_deleted == 0 and "returned no items" in run.error_summary
    assert all(d.status == DocumentStatus.READY for d in await env["docs"]())


@pytest.mark.asyncio
async def test_a_discovery_failure_midway_removes_nothing(env, world):
    for i in range(3):
        world.put(f"d{i}")
    await env["sync"]()
    world.discovery_error = ConnectorHttpError("listing failed halfway")

    status, run_id = await env["sync"]()
    run = await env["run"](run_id)

    assert status == "failed" and run.documents_deleted == 0 and "listing failed" in run.error_summary
    assert all(d.status == DocumentStatus.READY for d in await env["docs"]())
    assert (await env["source"]()).status == "error"


@pytest.mark.asyncio
async def test_most_of_a_large_source_disappearing_is_held_back_unless_allowed(env, world):
    for i in range(24):
        world.put(f"d{i}")
    await env["sync"]()
    for i in range(6, 24):
        del world.items[f"d{i}"]  # 18 of 24 vanish

    status, run_id = await env["sync"]()
    run = await env["run"](run_id)
    assert status == "partial" and run.documents_deleted == 0 and "held back" in run.error_summary

    await env["edit"](configuration={"bucket": "b", "allow_bulk_delete": True})
    _, run_id = await env["sync"]()
    assert (await env["run"](run_id)).documents_deleted == 18


@pytest.mark.asyncio
async def test_rejected_credentials_disconnect_the_source_and_are_reported_clearly(env, world):
    world.put("a")
    world.discovery_error = AuthenticationFailed("HTTP 401 from https://source.test/x: the credentials were rejected or lack access.")

    status, run_id = await env["sync"]()

    assert status == "failed"
    source = await env["source"]()
    assert source.status == "disconnected" and source.health["authentication"] == "invalid"
    assert source.last_sync_status == "failed"


@pytest.mark.asyncio
async def test_a_duplicate_delivery_of_the_same_run_does_nothing(env, world):
    world.put("a")
    _, run_id = await env["sync"]()
    engine = SyncEngine(env["container"], registry=ConnectorRegistry())
    assert await engine.run(env["source_id"], run_id) == "skipped"  # not `queued` any more


@pytest.mark.asyncio
async def test_cancellation_stops_between_documents_and_skips_the_removal_sweep(env, world):
    for i in range(6):
        world.put(f"d{i}")
    await env["sync"]()
    del world.items["d5"]  # would be archived by a completed sync
    world.cancel_after = 2

    status, run_id = await env["sync"]()

    assert status == "cancelled"
    assert (await env["run"](run_id)).documents_deleted == 0
    assert (await env["records"]())["d5"].status != "deleted"


# ------------------------------------------------------------------ incremental changes
@pytest.mark.asyncio
async def test_incremental_changes_are_applied_and_the_cursor_only_advances_on_success(env, world):
    world.put("a"), world.put("b")
    await env["sync"]()
    assert (await env["source"]()).sync_state["cursor"] == "after-full-listing"

    world.put("a", text="a changed", version="2")
    world.changes = [ExternalChange("updated", "a", world._doc_for("a") if hasattr(world, "_doc_for") else None), ExternalChange("deleted", "b")]
    world.changes[0].document = ExternalDocument(external_id="a", title="a", canonical_url="https://source.test/a", external_version="2", metadata={})
    _, run_id = await env["sync"]()

    run = await env["run"](run_id)
    assert counts(run) == (1, 0, 1, 1, 0, 0)  # only the change set was looked at
    by_id = {d.external_id: d for d in await env["docs"]() if d.is_current}
    assert by_id["b"].status == DocumentStatus.ARCHIVED and by_id["a"].external_version == "2"


# ------------------------------------------------------------------ permissions
@pytest.mark.asyncio
async def test_external_permissions_fail_closed_then_follow_identity_mappings(env, world):
    world.put("secret", permissions=[ExternalPermission("group", "finance-team", "read"), ExternalPermission("user", "cfo@corp.test", "read")])
    world.put("open", permissions=[])

    _, run_id = await env["sync"]()
    by_id = {d.external_id: d for d in await env["docs"]()}
    assert by_id["secret"].visibility == "restricted" and not by_id["secret"].allowed_roles and not by_id["secret"].allowed_users
    assert by_id["open"].visibility == "tenant"  # explicitly unrestricted
    assert (await env["run"](run_id)).stats["unmapped_principals"] == 2

    from packages.connectors.access import remap_access

    async with request_scoped_session(env["container"]) as session:
        session.add(IdentityMapping(tenant_id=env["tenant_id"], provider="s3", principal_type="group", external_id="finance-team", internal_type="role", internal_id="finance"))
        session.add(IdentityMapping(tenant_id=env["tenant_id"], provider="s3", principal_type="user", external_id="cfo@corp.test", internal_type="user", internal_id="user-42"))
        await session.flush()
        assert await remap_access(session, tenant_id=env["tenant_id"], provider="s3") == 1

    secret = {d.external_id: d for d in await env["docs"]()}["secret"]
    assert (secret.allowed_roles, secret.allowed_users) == (["finance"], ["user-42"])


@pytest.mark.asyncio
async def test_a_permission_change_alone_updates_access_without_reprocessing(env, world):
    world.put("a", permissions=[ExternalPermission("group", "eng", "read")])
    await env["sync"]()
    world.fetches.clear()

    world.put("a", permissions=[])  # restriction lifted at the source; content untouched
    _, run_id = await env["sync"]()

    run = await env["run"](run_id)
    assert counts(run) == (1, 0, 0, 0, 1, 0) and run.permissions_updated == 1
    (document,) = await env["docs"]()
    assert document.visibility == "tenant" and world.fetches == []
    async with request_scoped_session(env["container"]) as session:
        rules = (await session.execute(select(func.count()).select_from(DocumentAccessRule).where(DocumentAccessRule.tenant_id == env["tenant_id"]))).scalar_one()
    assert rules == 0  # "no restriction" is the absence of rules


@pytest.mark.asyncio
async def test_permission_mode_source_default_ignores_the_sources_own_permissions(env, world):
    await env["edit"](configuration={"bucket": "b", "permission_mode": "source_default", "default_visibility": "restricted", "default_allowed_roles": ["hr"]})
    world.put("a", permissions=[])

    await env["sync"]()

    (document,) = await env["docs"]()
    assert (document.visibility, document.allowed_roles) == ("restricted", ["hr"])


# ------------------------------------------------------------------ isolation
@pytest.mark.asyncio
async def test_credentials_are_bound_to_their_own_source_and_tenant(env):
    cipher = CredentialCipher(TEST_KEY)
    service = SourceCredentialService(cipher)
    other_tenant = uuid4()

    async with request_scoped_session(env["container"]) as session:
        mine = await session.get(KnowledgeSource, env["source_id"])
        await service.store(session, mine, kind="token", secret={"api_token": "MINE"}, actor_id=None)
        assert await service.load(session, mine) == {"api_token": "MINE"}

        # A source object of another tenant pretending to be this source id must not be able to read the secret.
        impostor = KnowledgeSource(id=mine.id, tenant_id=other_tenant, name="x", type="s3")
        with pytest.raises(CredentialScopeError):
            await service.load(session, impostor)

        stored = (await session.execute(select(SourceCredential).where(SourceCredential.source_id == mine.id))).scalar_one()
        assert "MINE" not in stored.ciphertext

        await service.revoke(session, mine)
        assert await service.load(session, mine) is None
        assert stored.ciphertext is None


# ------------------------------------------------------------------ targeted notifications
@pytest.mark.asyncio
async def test_a_notification_refreshes_only_the_named_items(env, world):
    for name in ("a", "b", "c"):
        world.put(name, text=f"{name} v1", version="1")
    await env["sync"]()
    (await env["source"]()).sync_state  # baseline cursor
    world.fetches.clear()

    world.put("b", text="b v2", version="2")
    status, run_id = await env["sync"](targets=["b"])
    run = await env["run"](run_id)

    assert status == "succeeded" and counts(run) == (1, 0, 1, 0, 0, 0)
    assert world.fetches == ["b"]  # nothing else was even looked at
    assert (await env["source"]()).sync_state["cursor"] == "after-full-listing"  # a shortcut never moves the sync cursor


@pytest.mark.asyncio
async def test_a_notification_about_a_removed_item_archives_it(env, world):
    world.put("a"), world.put("b")
    await env["sync"]()
    del world.items["b"]

    _, run_id = await env["sync"](targets=["b", "never-existed"])

    assert counts(await env["run"](run_id)) == (2, 0, 0, 1, 0, 0)
    assert {d.external_id: d for d in await env["docs"]()}["b"].status == DocumentStatus.ARCHIVED
    assert {d.external_id: d for d in await env["docs"]()}["a"].status == DocumentStatus.READY


@pytest.mark.asyncio
async def test_a_connector_that_cannot_fetch_one_item_falls_back_to_a_full_sync(env, world):
    world.put("a"), world.put("b")
    await env["sync"]()
    world.put("a", text="changed", version="2")
    world.no_single = True

    _, run_id = await env["sync"](targets=["a"])

    assert counts(await env["run"](run_id)) == (2, 0, 1, 0, 1, 0)  # both items were considered: a full pass


@pytest.mark.asyncio
async def test_notifications_that_arrive_during_a_sync_are_applied_right_after_it(env, world):
    from packages.connectors.scheduling import add_pending_targets

    world.put("a", version="1"), world.put("b", text="b v1", version="1")
    await env["sync"]()

    async def notification_arrives_mid_sync():
        world.put("b", text="b v2", version="2")  # b changes while the sync is already running...
        await add_pending_targets(env["container"], env["source_id"], env["tenant_id"], ["b"])  # ...and the source tells us

    world.on_discover = notification_arrives_mid_sync
    _, first_run = await env["sync"]()
    world.on_discover = None

    async with request_scoped_session(env["container"]) as session:
        runs = (await session.execute(select(SourceSyncRun).where(SourceSyncRun.source_id == env["source_id"]).order_by(SourceSyncRun.created_at))).scalars().all()
    follow_up = runs[-1]
    assert follow_up.id != first_run and follow_up.trigger == "webhook" and follow_up.stats["targets"] == ["b"]
    assert follow_up.status == "succeeded"
    versions = [d.external_version for d in await env["docs"]() if d.external_id == "b"]
    assert versions == ["1", "2"]
    assert (await env["source"]()).sync_state.get("pending_targets") == []  # nothing left waiting


# ------------------------------------------------------------------ scale
@pytest.mark.asyncio
async def test_a_large_source_syncs_correctly_and_a_repeat_sync_is_cheap(env, world):
    import os
    import time

    n = int(os.environ.get("LOAD_ITEMS", "300"))
    for i in range(n):
        world.put(f"item-{i:05d}", text=f"document {i} body", version="1")

    started = time.monotonic()
    status, run_id = await env["sync"]()
    first = time.monotonic() - started
    assert status == "succeeded" and counts(await env["run"](run_id)) == (n, n, 0, 0, 0, 0)

    world.fetches.clear()
    started = time.monotonic()
    _, run_id = await env["sync"]()
    repeat = time.monotonic() - started
    assert counts(await env["run"](run_id)) == (n, 0, 0, 0, n, 0) and world.fetches == []  # nothing fetched or embedded again

    world.put("item-00007", text="changed", version="2")
    del world.items["item-00042"]
    _, run_id = await env["sync"]()
    assert counts(await env["run"](run_id)) == (n - 1, 0, 1, 1, n - 2, 0)

    print(f"LOAD {n} items: first sync {first:.1f}s ({n / first:.0f}/s), unchanged repeat {repeat:.1f}s ({n / repeat:.0f}/s)")
