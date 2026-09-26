from __future__ import annotations

from uuid import uuid4

import pytest

from packages.application.services.retrieval_log_service import (
    MAX_LOGGED_CANDIDATES,
    CandidateRecord,
    RetrievalLogService,
    RetrievalRecord,
    hash_query,
)
from packages.domain.models.retrieval_log import RetrievalLog, RetrievalResultLog


class _Session:
    def __init__(self):
        self.added = []
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass

    async def commit(self):
        self.committed = True


def _candidate(rank, selected=False):
    return CandidateRecord(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=rank,
        retrieval_rank=rank,
        retrieval_score=1.0 / rank,
        reranker_score=0.5 if selected else None,
        final_rank=rank if selected else None,
        selected=selected,
    )


def _record(candidates):
    return RetrievalRecord(
        tenant_id=uuid4(),
        query="What is the leave policy?",
        strategy="hybrid",
        top_k=5,
        reranking_enabled=True,
        candidates=candidates,
    )


def test_query_hash_is_stable_and_not_the_query():
    assert hash_query("Leave Policy ") == hash_query("leave policy")
    assert "leave" not in hash_query("leave policy")


@pytest.mark.asyncio
async def test_record_stores_hash_not_query_text_and_all_candidates():
    session = _Session()
    rec = _record([_candidate(1, selected=True), _candidate(2)])

    await RetrievalLogService(lambda: session).record(rec)

    log = next(o for o in session.added if isinstance(o, RetrievalLog))
    results = [o for o in session.added if isinstance(o, RetrievalResultLog)]
    assert session.committed
    assert log.id == rec.retrieval_id
    assert log.query_hash == hash_query(rec.query)
    assert "leave" not in repr(log.query_hash)
    assert (log.candidate_count, log.selected_count) == (2, 1)
    assert {r.retrieval_id for r in results} == {rec.retrieval_id}
    assert {r.selected_for_context for r in results} == {True, False}
    assert all(r.tenant_id == rec.tenant_id for r in results)


@pytest.mark.asyncio
async def test_cap_never_drops_a_chunk_that_was_used():
    session = _Session()
    candidates = [_candidate(i) for i in range(1, MAX_LOGGED_CANDIDATES + 21)]
    candidates[-1].selected = True  # the worst-ranked candidate was still selected

    await RetrievalLogService(lambda: session).record(_record(candidates))

    results = [o for o in session.added if isinstance(o, RetrievalResultLog)]
    assert len(results) == MAX_LOGGED_CANDIDATES
    assert any(r.selected_for_context for r in results)


@pytest.mark.asyncio
async def test_a_failing_database_never_breaks_retrieval():
    class Broken:
        async def __aenter__(self):
            raise RuntimeError("db down")

        async def __aexit__(self, *exc):
            return False

    await RetrievalLogService(lambda: Broken()).record(_record([_candidate(1)]))  # must not raise
