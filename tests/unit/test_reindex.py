"""
run_reindex (packages/application/services/reindex.py) — zero test coverage before this
(docs/BUGS.md F3). Its branching is small but consequential: a not-found document must return
False and write no audit event at all; a success must audit "document.reindexed"; a failure must
audit "document.reindex_failed" with the failing stage, but ONLY once a tenant_id is actually known
(a failure before the document lookup even completes has nothing to attribute the audit event to).

A fake container stands in for the real one — the real `ingestion_pipeline().reindex_document()`
path is a full load->clean->split->embed->store run against live embedding APIs, out of scope for
a unit test of this function's own control flow. `request_scoped_session` is monkeypatched to a
no-op context manager since these fakes never touch a real session.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from packages.application.services import reindex as reindex_module
from packages.application.services.reindex import run_reindex


class _FakeAuditService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def record(self, **kwargs):
        self.calls.append(kwargs)


def _fake_container(*, document, reindex_error: Exception | None = None):
    document_repo = SimpleNamespace(get=_async_return(document))

    async def _reindex_document(document_id):
        if reindex_error is not None:
            raise reindex_error

    ingestion_pipeline = SimpleNamespace(reindex_document=_reindex_document)
    audit = _FakeAuditService()

    return SimpleNamespace(
        repositories=SimpleNamespace(document=lambda: document_repo),
        rag=SimpleNamespace(ingestion_pipeline=lambda: ingestion_pipeline),
        audit=lambda: audit,
    ), audit


def _async_return(value):
    async def _get(_document_id):
        return value

    return _get


@pytest.fixture(autouse=True)
def _noop_request_scoped_session(monkeypatch):
    @asynccontextmanager
    async def _noop(_container):
        yield None

    monkeypatch.setattr(reindex_module, "request_scoped_session", _noop)


@pytest.mark.asyncio
async def test_a_missing_document_returns_false_and_audits_nothing():
    container, audit = _fake_container(document=None)

    result = await run_reindex(container, uuid4(), uuid4())

    assert result is False
    assert audit.calls == []


@pytest.mark.asyncio
async def test_success_returns_true_and_audits_reindexed_for_the_documents_own_tenant():
    tenant_id, document_id, actor_id = uuid4(), uuid4(), uuid4()
    document = SimpleNamespace(tenant_id=tenant_id, file_name="policy.pdf")
    container, audit = _fake_container(document=document)

    result = await run_reindex(container, document_id, actor_id)

    assert result is True
    assert len(audit.calls) == 1
    call = audit.calls[0]
    assert call["tenant_id"] == tenant_id
    assert call["actor_id"] == actor_id
    assert call["action"] == "document.reindexed"
    assert call["resource_id"] == document_id
    assert call["detail"] == {"file_name": "policy.pdf", "trigger": "manual"}


@pytest.mark.asyncio
async def test_a_pipeline_failure_returns_false_and_audits_reindex_failed_with_its_stage():
    tenant_id, document_id, actor_id = uuid4(), uuid4(), uuid4()
    document = SimpleNamespace(tenant_id=tenant_id, file_name="policy.pdf")

    class _StageError(Exception):
        ingestion_stage = "embedding"

    container, audit = _fake_container(document=document, reindex_error=_StageError("embed failed"))

    result = await run_reindex(container, document_id, actor_id)

    assert result is False
    assert len(audit.calls) == 1
    call = audit.calls[0]
    assert call["action"] == "document.reindex_failed"
    assert call["tenant_id"] == tenant_id
    assert call["detail"] == {"file_name": "policy.pdf", "stage": "embedding"}


@pytest.mark.asyncio
async def test_a_pipeline_failure_with_no_stage_attribute_falls_back_to_unknown():
    tenant_id, document_id, actor_id = uuid4(), uuid4(), uuid4()
    document = SimpleNamespace(tenant_id=tenant_id, file_name="policy.pdf")
    container, audit = _fake_container(document=document, reindex_error=RuntimeError("boom"))

    await run_reindex(container, document_id, actor_id)

    assert audit.calls[0]["detail"]["stage"] == "unknown"


@pytest.mark.asyncio
async def test_a_failure_before_the_document_lookup_resolves_audits_nothing(monkeypatch):
    document_id, actor_id = uuid4(), uuid4()

    async def _broken_get(_document_id):
        raise RuntimeError("db down")

    document_repo = SimpleNamespace(get=_broken_get)
    audit = _FakeAuditService()
    container = SimpleNamespace(
        repositories=SimpleNamespace(document=lambda: document_repo),
        rag=SimpleNamespace(ingestion_pipeline=lambda: SimpleNamespace(reindex_document=None)),
        audit=lambda: audit,
    )

    result = await run_reindex(container, document_id, actor_id)

    assert result is False
    assert audit.calls == []
