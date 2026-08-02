"""
scripts/evaluate_retrieval.py

Retrieval Evaluation (docs/mvpRAG.md v1.1) — a standalone script, not
a pytest suite (this repo has no pytest wiring at all yet, see
docs/BUILD_STATUS.md Phase 15; adding that is a separate, larger
concern). Runs each labeled query in eval/retrieval_dataset.json
through the exact same retrieval path packages/api/routers/search.py
uses (KnowledgeManager.search() + CrossEncoderReranker.rerank()),
computes precision@k/recall@k against each query's
expected_document_ids, and writes a timestamped JSON report to
storage/eval/ so chunking/ranking changes can be measured run-over-run
instead of vibes-checked.

The shipped eval/retrieval_dataset.json is a small real example (not
synthetic) against whatever's already ingested in a given database —
extend it with your own tenant_id/query/expected_document_ids as you
ingest real content.

Usage:
    python scripts/evaluate_retrieval.py [path/to/dataset.json] [--k N]
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from packages.api.dependencies import request_scoped_session
from packages.conversation.bootstrap import ensure_default_model_profile
from packages.infrastructure.container import ApplicationContainer
from packages.knowledge.vectorstores.schema import SearchFilter, SearchOptions
from packages.shared.logging import get_logger

logger = get_logger(__name__)

DEFAULT_DATASET = Path(__file__).resolve().parent.parent / "eval" / "retrieval_dataset.json"
REPORT_DIR = Path(__file__).resolve().parent.parent / "storage" / "eval"


def _precision_recall(retrieved_ids: list[str], expected_ids: set[str]) -> tuple[float, float]:
    if not retrieved_ids:
        return 0.0, 0.0

    retrieved_set = set(retrieved_ids)
    hits = len(retrieved_set & expected_ids)

    precision = hits / len(retrieved_set)
    recall = hits / len(expected_ids) if expected_ids else 0.0

    return precision, recall


async def evaluate(dataset_path: Path, k: int) -> dict:
    with open(dataset_path, encoding="utf-8") as f:
        cases = json.load(f)

    container = ApplicationContainer()
    results = []

    async with request_scoped_session(container):
        knowledge_manager = container.rag.knowledge_manager()
        reranker = container.rag.reranker()
        model_profiles = container.repositories.model_profile()
        model_profile = await ensure_default_model_profile(model_profiles)

        for case in cases:
            query = case["query"]
            tenant_id = UUID(case["tenant_id"])
            expected_ids = set(case.get("expected_document_ids", []))

            filters = SearchFilter(tenant_id=tenant_id, model_profile_id=model_profile.id)

            candidates = await knowledge_manager.search(
                query=query,
                filters=filters,
                options=SearchOptions(limit=max(k * 2, 10)),
            )
            reranked = await reranker.rerank(query, candidates, top_k=k)

            retrieved_ids = [str(r.chunk.document_id) for r in reranked]
            precision, recall = _precision_recall(retrieved_ids, expected_ids)

            results.append(
                {
                    "query": query,
                    "expected_document_ids": sorted(expected_ids),
                    "retrieved_document_ids": retrieved_ids,
                    "precision_at_k": round(precision, 4),
                    "recall_at_k": round(recall, 4),
                }
            )

    avg_precision = sum(r["precision_at_k"] for r in results) / len(results) if results else 0.0
    avg_recall = sum(r["recall_at_k"] for r in results) / len(results) if results else 0.0

    return {
        "dataset": str(dataset_path),
        "k": k,
        "case_count": len(results),
        "avg_precision_at_k": round(avg_precision, 4),
        "avg_recall_at_k": round(avg_recall, 4),
        "cases": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score retrieval quality against a labeled query set.")
    parser.add_argument(
        "dataset",
        nargs="?",
        default=str(DEFAULT_DATASET),
        help="Path to a labeled JSON dataset (default: eval/retrieval_dataset.json).",
    )
    parser.add_argument("--k", type=int, default=5, help="Top-k results to evaluate against (default: 5).")
    args = parser.parse_args()

    report = asyncio.run(evaluate(Path(args.dataset), args.k))

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = REPORT_DIR / f"retrieval_eval_{timestamp}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Avg precision@{args.k}: {report['avg_precision_at_k']}")
    print(f"Avg recall@{args.k}:    {report['avg_recall_at_k']}")
    print(f"Report written to {report_path}")


if __name__ == "__main__":
    main()
