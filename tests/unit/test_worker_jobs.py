"""
packages/worker/jobs.py — zero test coverage before this (docs/BUGS.md item 19) despite being
every scheduled maintenance job this platform runs in production: retention purge, stale-reindex
sweep, scratch-file cleanup, stale-upload-job cleanup, and crash recovery for stuck conversations
(the last of which already caused one real, documented live bug - a duplicate assistant message -
with no regression test guarding against it recurring).

Fakes stand in for the real `ApplicationContainer`, matching the pattern already established in
tests/unit/test_reindex.py: each job function only duck-types `ctx["container"]`, so a
`SimpleNamespace` tree is enough to exercise its own orchestration logic (what it queries, what it
calls, what it counts, that a failure in one item doesn't stop the sweep) without a real Postgres
checkpointer or a real ingestion pipeline. `request_scoped_session` and `create_postgres_checkpointer`
are monkeypatched to no-ops/fakes since these tests are about jobs.py's own control flow, not the
repository/service layers already covered elsewhere.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from packages.application.services import retention_service as retention_module
from packages.worker import jobs as jobs_module


@pytest.fixture(autouse=True)
def _noop_request_scoped_session(monkeypatch):
    @asynccontextmanager
    async def _noop(_container):
        yield None

    monkeypatch.setattr(jobs_module, "request_scoped_session", _noop)


# ------------------------------------------------------------------ cleanup_orphaned_scratch_files
@pytest.mark.asyncio
async def test_scratch_cleanup_deletes_only_files_older_than_the_threshold(tmp_path, monkeypatch):
    old_file = tmp_path / "old.tmp"
    fresh_file = tmp_path / "fresh.tmp"
    old_file.write_text("x")
    fresh_file.write_text("x")
    old_time = time.time() - jobs_module._MAX_AGE_SECONDS - 60
    import os

    os.utime(old_file, (old_time, old_time))
    monkeypatch.setattr(jobs_module.settings.storage, "temp_directory", tmp_path)

    result = await jobs_module.cleanup_orphaned_scratch_files({})

    assert result == {"checked": 2, "deleted": 1}
    assert not old_file.exists()
    assert fresh_file.exists()


@pytest.mark.asyncio
async def test_scratch_cleanup_is_a_harmless_no_op_when_the_directory_does_not_exist(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs_module.settings.storage, "temp_directory", tmp_path / "does-not-exist")

    result = await jobs_module.cleanup_orphaned_scratch_files({})

    assert result == {"checked": 0, "deleted": 0}


# ------------------------------------------------------------------ cleanup_stale_upload_jobs_job
class _FakeUploadJobRepo:
    def __init__(self, stale) -> None:
        self._stale = stale
        self.failed: list[tuple] = []

    async def list_stale(self, cutoff):
        self.last_cutoff = cutoff
        return self._stale

    async def mark_failed(self, job, reason):
        self.failed.append((job, reason))


@pytest.mark.asyncio
async def test_cleanup_stale_upload_jobs_marks_every_stale_job_failed():
    repo = _FakeUploadJobRepo([SimpleNamespace(id=uuid4()), SimpleNamespace(id=uuid4())])
    container = SimpleNamespace(repositories=SimpleNamespace(upload_job=lambda: repo))

    result = await jobs_module.cleanup_stale_upload_jobs_job({"container": container})

    assert result == {"failed": 2}
    assert len(repo.failed) == 2
    assert all("Stale" in reason for _job, reason in repo.failed)


@pytest.mark.asyncio
async def test_cleanup_stale_upload_jobs_is_a_no_op_when_nothing_is_stale():
    repo = _FakeUploadJobRepo([])
    container = SimpleNamespace(repositories=SimpleNamespace(upload_job=lambda: repo))

    result = await jobs_module.cleanup_stale_upload_jobs_job({"container": container})

    assert result == {"failed": 0}


# ------------------------------------------------------------------ purge_expired_logs_job
class _FakePlatformSettings:
    def __init__(self, values: dict) -> None:
        self._values = values

    async def get(self, key):
        return self._values[key]


@pytest.mark.asyncio
async def test_purge_expired_logs_job_forwards_the_platform_settings_values_correctly(monkeypatch):
    captured = {}

    async def _fake_purge_expired(session_factory, *, now=None, retrieval_log_days=None, audit_days=None):
        captured["retrieval_log_days"] = retrieval_log_days
        captured["audit_days"] = audit_days
        return {"retrieval_logs": 3, "retrieval_results": 7, "audit_events": 2}

    monkeypatch.setattr(retention_module, "purge_expired", _fake_purge_expired)
    settings_service = _FakePlatformSettings({"retention_retrieval_log_days": 42, "retention_audit_days": 99})
    container = SimpleNamespace(
        database=SimpleNamespace(session_factory=lambda: "fake-factory"),
        platform_settings=SimpleNamespace(service=lambda: settings_service),
    )

    result = await jobs_module.purge_expired_logs_job({"container": container})

    # retention_retrieval_log_days must land on retrieval_log_days, not get swapped with audit_days -
    # exactly the kind of wiring bug a thin pass-through job can silently ship with no test catching it.
    assert captured == {"retrieval_log_days": 42, "audit_days": 99}
    assert result == {"retrieval_logs": 3, "retrieval_results": 7, "audit_events": 2}


# ------------------------------------------------------------------ reindex_stale_documents_job
class _FakeDocumentRepo:
    def __init__(self, stale) -> None:
        self._stale = stale

    async def list_stale(self, cutoff):
        self.last_cutoff = cutoff
        return self._stale


def _fake_reindex_container(*, stale_documents, reindex_error_for: set[str] | None = None):
    reindex_error_for = reindex_error_for or set()
    audit = SimpleNamespace(calls=[])

    async def _record(**kwargs):
        audit.calls.append(kwargs)

    audit.record = _record

    async def _reindex_document(document_id):
        if str(document_id) in reindex_error_for:
            raise RuntimeError(f"boom {document_id}")

    settings_service = _FakePlatformSettings({"reindex_stale_after_days": 90})
    return SimpleNamespace(
        repositories=SimpleNamespace(document=lambda: _FakeDocumentRepo(stale_documents)),
        rag=SimpleNamespace(ingestion_pipeline=lambda: SimpleNamespace(reindex_document=_reindex_document)),
        audit=lambda: audit,
        platform_settings=SimpleNamespace(service=lambda: settings_service),
    ), audit


@pytest.mark.asyncio
async def test_reindex_stale_documents_reindexes_every_stale_document_and_audits_each_one():
    doc1 = SimpleNamespace(id=uuid4(), tenant_id=uuid4(), file_name="a.pdf")
    doc2 = SimpleNamespace(id=uuid4(), tenant_id=uuid4(), file_name="b.pdf")
    container, audit = _fake_reindex_container(stale_documents=[doc1, doc2])

    result = await jobs_module.reindex_stale_documents_job({"container": container})

    assert result == {"reindexed": 2, "failed": 0}
    assert len(audit.calls) == 2
    assert all(c["action"] == "document.reindexed" and c["detail"]["trigger"] == "scheduled" for c in audit.calls)


@pytest.mark.asyncio
async def test_a_failing_document_does_not_stop_the_sweep_and_is_not_audited_as_reindexed():
    doc1 = SimpleNamespace(id=uuid4(), tenant_id=uuid4(), file_name="bad.pdf")
    doc2 = SimpleNamespace(id=uuid4(), tenant_id=uuid4(), file_name="good.pdf")
    container, audit = _fake_reindex_container(stale_documents=[doc1, doc2], reindex_error_for={str(doc1.id)})

    result = await jobs_module.reindex_stale_documents_job({"container": container})

    assert result == {"reindexed": 1, "failed": 1}
    assert len(audit.calls) == 1
    assert audit.calls[0]["resource_id"] == doc2.id


@pytest.mark.asyncio
async def test_reindex_stale_documents_is_a_no_op_when_nothing_is_stale():
    container, audit = _fake_reindex_container(stale_documents=[])

    result = await jobs_module.reindex_stale_documents_job({"container": container})

    assert result == {"reindexed": 0, "failed": 0}
    assert audit.calls == []


# ------------------------------------------------------------------ recover_stuck_conversations_job
class _FakeCheckpointerConn:
    def __init__(self) -> None:
        self.closed = False

    def close(self):
        self.closed = True


class _FakeCheckpointer:
    def __init__(self) -> None:
        self.conn = _FakeCheckpointerConn()
        self.deleted_threads: list[str] = []

    async def adelete_thread(self, thread_id: str) -> None:
        self.deleted_threads.append(thread_id)


class _FakeCheckpointerProvider:
    """Stands in for the dependency_injector `container.graph.checkpointer` provider."""

    def __init__(self) -> None:
        self.overridden_with = None
        self.reset = False

    def override(self, provider_object) -> None:
        self.overridden_with = provider_object

    def reset_override(self) -> None:
        self.reset = True


class _FakeConversationRepoForRecovery:
    def __init__(self, stuck) -> None:
        self._stuck = stuck

    async def list_stuck_processing(self, cutoff):
        self.last_cutoff = cutoff
        return self._stuck


def _fake_recovery_container(*, stuck, recover_results: dict):
    """`recover_results` maps conversation id -> a response object, None, or an Exception to raise."""

    async def _recover(conversation_id):
        outcome = recover_results[conversation_id]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    chat_service = SimpleNamespace(recover=_recover)
    checkpointer_provider = _FakeCheckpointerProvider()
    return SimpleNamespace(
        repositories=SimpleNamespace(conversation=lambda: _FakeConversationRepoForRecovery(stuck)),
        chat_service=SimpleNamespace(chat_service=lambda: chat_service),
        graph=SimpleNamespace(checkpointer=checkpointer_provider),
    ), checkpointer_provider


@pytest.fixture
def _fake_checkpointer(monkeypatch):
    checkpointer = _FakeCheckpointer()

    async def _create():
        return checkpointer

    monkeypatch.setattr(jobs_module, "create_postgres_checkpointer", _create)
    return checkpointer


@pytest.mark.asyncio
async def test_recovers_a_genuinely_stuck_conversation(_fake_checkpointer):
    cid = uuid4()
    container, checkpointer_provider = _fake_recovery_container(
        stuck=[SimpleNamespace(id=cid)], recover_results={cid: SimpleNamespace(message="resumed")}
    )

    result = await jobs_module.recover_stuck_conversations_job({"container": container})

    assert result == {"recovered": 1, "already_complete": 0, "failed": 0}
    assert checkpointer_provider.reset is True  # override always cleaned up, even on success


@pytest.mark.asyncio
async def test_an_already_complete_thread_just_clears_the_marker_not_a_duplicate_message(_fake_checkpointer):
    """
    Regression guard for the exact live bug documented on recover_stuck_conversations_job's own
    docstring: ChatService.recover() returning None (graph already reached END) must be counted as
    already_complete, never recovered - counting it as recovered is precisely what previously
    produced a real duplicate assistant message in production.
    """
    cid = uuid4()
    container, _ = _fake_recovery_container(stuck=[SimpleNamespace(id=cid)], recover_results={cid: None})

    result = await jobs_module.recover_stuck_conversations_job({"container": container})

    assert result == {"recovered": 0, "already_complete": 1, "failed": 0}


@pytest.mark.asyncio
async def test_one_conversations_recovery_failure_does_not_stop_the_sweep(_fake_checkpointer):
    bad_cid, good_cid = uuid4(), uuid4()
    container, _ = _fake_recovery_container(
        stuck=[SimpleNamespace(id=bad_cid), SimpleNamespace(id=good_cid)],
        recover_results={bad_cid: RuntimeError("graph crashed again"), good_cid: SimpleNamespace(message="ok")},
    )

    result = await jobs_module.recover_stuck_conversations_job({"container": container})

    assert result == {"recovered": 1, "already_complete": 0, "failed": 1}


@pytest.mark.asyncio
async def test_the_checkpointer_override_is_reset_and_connection_closed_even_when_nothing_is_stuck(_fake_checkpointer):
    container, checkpointer_provider = _fake_recovery_container(stuck=[], recover_results={})

    result = await jobs_module.recover_stuck_conversations_job({"container": container})

    assert result == {"recovered": 0, "already_complete": 0, "failed": 0}
    assert checkpointer_provider.reset is True
    assert _fake_checkpointer.conn.closed is True


# ------------------------------------------------------------------ expire_stale_conversations_job
class _FakeConversationRepoForExpiry:
    def __init__(self, stale) -> None:
        self._stale = stale
        self.marked: list[tuple] = []

    async def list_stale_active(self, cutoff):
        self.last_cutoff = cutoff
        return self._stale

    async def mark_status(self, conversation, status):
        self.marked.append((conversation, status))


@pytest.mark.asyncio
async def test_expires_every_stale_conversation_and_frees_its_checkpoint(_fake_checkpointer):
    from packages.domain.enums.conversation_status import ConversationStatus

    c1, c2 = SimpleNamespace(id=uuid4()), SimpleNamespace(id=uuid4())
    repo = _FakeConversationRepoForExpiry([c1, c2])
    settings_service = _FakePlatformSettings({"session_expiry_days": 30})
    container = SimpleNamespace(
        repositories=SimpleNamespace(conversation=lambda: repo),
        platform_settings=SimpleNamespace(service=lambda: settings_service),
    )

    result = await jobs_module.expire_stale_conversations_job({"container": container})

    assert result == {"expired": 2}
    assert [status for _c, status in repo.marked] == [ConversationStatus.ARCHIVED, ConversationStatus.ARCHIVED]
    assert sorted(_fake_checkpointer.deleted_threads) == sorted([str(c1.id), str(c2.id)])
    assert _fake_checkpointer.conn.closed is True


@pytest.mark.asyncio
async def test_expire_stale_conversations_is_a_no_op_when_nothing_is_stale(_fake_checkpointer):
    repo = _FakeConversationRepoForExpiry([])
    settings_service = _FakePlatformSettings({"session_expiry_days": 30})
    container = SimpleNamespace(
        repositories=SimpleNamespace(conversation=lambda: repo),
        platform_settings=SimpleNamespace(service=lambda: settings_service),
    )

    result = await jobs_module.expire_stale_conversations_job({"container": container})

    assert result == {"expired": 0}
    assert _fake_checkpointer.conn.closed is True  # the connection is still closed, nothing leaks
