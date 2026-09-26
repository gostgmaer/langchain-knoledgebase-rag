"""
scripts/evaluate_retrieval.py

Retrieval evaluation: scores retrieval against a labelled query set, so ranking/chunking changes are
measured instead of guessed, and compares three configurations on the same questions:

    vector          dense similarity only
    hybrid          dense + BM25 fused with reciprocal rank fusion (what production retrieves with)
    hybrid+rerank   hybrid, then the cross-encoder (what production answers from)

Metrics, all at document level (a document counts once, at its best-ranked chunk), at cut-off k:
    hit@k        share of queries with at least one expected document in the top k
    recall@k     share of the expected documents found in the top k, averaged
    precision@k  share of the (distinct) documents in the top k that are expected, averaged
    MRR          mean reciprocal rank of the first expected document (0 when absent)
    NDCG@k       rank-aware gain with binary relevance

A dataset case is  {"query": "...", "expected_documents": ["file name", ...]}  (names are resolved
against the tenant's current documents) or, for pinned data, "expected_document_ids": [...].
Run it inside the api container so it reaches the same database:

    docker compose exec api sh -c "cd /app && PYTHONPATH=. python scripts/evaluate_retrieval.py eval/retrieval_eval_set.json \
        --tenant-id <tenant uuid> [--k 5]

`scripts/eval_corpus.sh up` loads the bundled corpus (eval/corpus) that the bundled eval set
(eval/retrieval_eval_set.json) is labelled against. A small set measures direction, not truth: add
questions from your own documents before drawing conclusions.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from packages.api.dependencies import request_scoped_session
from packages.conversation.bootstrap import ensure_default_model_profile
from packages.infrastructure.container import ApplicationContainer
from packages.knowledge.vectorstores.schema import SearchFilter, SearchOptions
from packages.shared.access import set_can_read_restricted
from packages.shared.logging import get_logger

logger = get_logger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = ROOT / "eval" / "retrieval_eval_set.json"
REPORT_DIR = ROOT / "storage" / "eval"
MODES = ("vector", "hybrid", "hybrid+rerank")


def distinct_documents(ranked_document_ids: list[str], k: int) -> list[str]:
    """Order-preserving de-duplication, then the first k: a document counts once, at its best chunk."""
    seen: dict[str, None] = {}
    for doc_id in ranked_document_ids:
        seen.setdefault(doc_id, None)
    return list(seen)[:k]


def score_case(ranked_document_ids: list[str], expected: set[str], k: int) -> dict[str, float]:
    top = distinct_documents(ranked_document_ids, k)
    hits = [doc in expected for doc in top]
    found = sum(hits)

    first = next((i for i, hit in enumerate(hits, start=1) if hit), None)
    dcg = sum(1 / math.log2(i + 1) for i, hit in enumerate(hits, start=1) if hit)
    ideal = sum(1 / math.log2(i + 1) for i in range(1, min(len(expected), k) + 1))

    return {
        "hit": 1.0 if found else 0.0,
        "recall": found / len(expected) if expected else 0.0,
        "precision": found / len(top) if top else 0.0,
        "mrr": 1 / first if first else 0.0,
        "ndcg": dcg / ideal if ideal else 0.0,
    }


def summarise(cases: list[dict[str, float]]) -> dict[str, float]:
    if not cases:
        return {name: 0.0 for name in ("hit", "recall", "precision", "mrr", "ndcg")}
    return {name: round(sum(c[name] for c in cases) / len(cases), 4) for name in cases[0]}


async def evaluate(dataset_path: Path, k: int, tenant_id: UUID | None) -> dict:
    cases = json.loads(dataset_path.read_text(encoding="utf-8"))

    # Evaluation is an operator tool: it may see restricted documents.
    set_can_read_restricted(True)

    container = ApplicationContainer()
    per_mode: dict[str, list[dict]] = {mode: [] for mode in MODES}
    unresolved: list[str] = []

    async with request_scoped_session(container):
        knowledge = container.rag.knowledge_manager()
        reranker = container.rag.reranker()
        vector_store = knowledge.retriever_manager.retriever.vector_store
        profile = await ensure_default_model_profile(container.repositories.model_profile())
        documents = container.repositories.document()

        names_by_tenant: dict[UUID, dict[str, str]] = {}

        for case in cases:
            tenant = tenant_id or UUID(case["tenant_id"])
            if tenant not in names_by_tenant:
                rows = await documents.list_by_tenant(tenant, limit=200, offset=0)
                names_by_tenant[tenant] = {d.file_name: str(d.id) for d in rows if d.is_current}
            by_name = names_by_tenant[tenant]

            expected = set(case.get("expected_document_ids", []))
            for name in case.get("expected_documents", []):
                if name in by_name:
                    expected.add(by_name[name])
                else:
                    unresolved.append(name)
            if not expected:
                continue

            filters = SearchFilter(tenant_id=tenant, model_profile_id=profile.id)
            query = case["query"]
            pool = SearchOptions(limit=max(k * 3, 15))

            embedding = await knowledge.embedding_manager.embed_query(query)
            vector = await vector_store.similarity_search(query_embedding=embedding, filters=filters, options=pool)
            hybrid = await knowledge.search(query=query, filters=filters, options=pool)
            reranked = await reranker.rerank(query, hybrid, top_k=max(k * 3, 15))

            for mode, results in zip(MODES, (vector, hybrid, reranked), strict=True):
                ranked = [str(r.chunk.document_id) for r in results]
                per_mode[mode].append(
                    {"query": query, "top": distinct_documents(ranked, k), **score_case(ranked, expected, k)}
                )

    return {
        "dataset": str(dataset_path),
        "k": k,
        "case_count": len(per_mode["hybrid"]),
        "unresolved_expected_documents": sorted(set(unresolved)),
        "summary": {mode: summarise([{m: c[m] for m in ("hit", "recall", "precision", "mrr", "ndcg")} for c in rows])
                    for mode, rows in per_mode.items()},
        "cases": per_mode,
    }


def print_report(report: dict) -> None:
    k = report["k"]
    print(f"\n{report['case_count']} queries, k={k}\n")
    print(f"{'mode':<16}{'hit@k':>8}{'recall@k':>10}{'prec@k':>9}{'MRR':>8}{'NDCG@k':>9}")
    for mode, s in report["summary"].items():
        print(f"{mode:<16}{s['hit']:>8}{s['recall']:>10}{s['precision']:>9}{s['mrr']:>8}{s['ndcg']:>9}")
    if report["unresolved_expected_documents"]:
        print("\nNot found in the tenant (upload them first):", ", ".join(report["unresolved_expected_documents"]))
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Score retrieval quality against a labelled query set.")
    parser.add_argument("dataset", nargs="?", default=str(DEFAULT_DATASET), help="Labelled JSON dataset.")
    parser.add_argument("--k", type=int, default=5, help="Cut-off (default 5).")
    parser.add_argument("--tenant-id", type=UUID, default=None, help="Tenant to evaluate (overrides the dataset's).")
    args = parser.parse_args()

    report = asyncio.run(evaluate(Path(args.dataset), args.k, args.tenant_id))

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"retrieval_eval_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print_report(report)
    print(f"Report written to {path}")


if __name__ == "__main__":
    main()
