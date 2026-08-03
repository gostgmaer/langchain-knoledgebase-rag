# multi_vector.py
from __future__ import annotations

from dataclasses import replace

from packages.knowledge.retrievers.base import BaseRetriever
from packages.knowledge.retrievers.schemas import RetrievalRequest
from packages.knowledge.vectorstores.manager import VectorStoreManager
from packages.knowledge.vectorstores.schema import SearchOptions, SearchResult

_PRIMARY_CANDIDATES_PER_DOCUMENT = 5
_PRIMARY_RESULTS_PER_DOCUMENT = 2


class MultiVectorRetriever(BaseRetriever):
    """
    Resolves a document-level summary hit (Multi Vector Retriever, v1
    scope: one extra representation per document, docs/mvpRAG.md
    v2.0 — see IngestionPipeline._store_summary_representation()) back
    to that document's real top-scoring primary chunk(s), before
    results ever reach the LLM/citations. A query matching the
    *summary's* phrasing rather than any single chunk's literal
    wording still surfaces the right document, but the synthetic
    summary text itself is never returned as literal context — it
    isn't something that should be cited or quoted as if it were part
    of the source document.
    """

    def __init__(
        self,
        inner: BaseRetriever,
        vector_store: VectorStoreManager,
    ) -> None:
        self._inner = inner
        self._vector_store = vector_store

    async def retrieve(
        self,
        request: RetrievalRequest,
    ) -> list[SearchResult]:

        matches = await self._inner.retrieve(request)

        # Keyed by chunk id, keeping whichever score is higher — a
        # document can legitimately appear twice in `matches` (once
        # via its summary hit, once via a real primary chunk the
        # inner retriever *also* matched directly), and resolving the
        # summary hit below can independently re-surface that exact
        # same primary chunk again. Without deduping here, a caller
        # using this retriever directly (not through RetrieveNode,
        # which happens to dedupe its own multi-query merge by chunk
        # id too) would see literal duplicate content — confirmed live
        # while building this: a single-chunk document's one real
        # chunk came back twice, at two different scores, from one
        # search() call.
        deduped: dict[object, SearchResult] = {}

        def _keep_best(result: SearchResult) -> None:
            existing = deduped.get(result.chunk.id)
            if existing is None or result.score > existing.score:
                deduped[result.chunk.id] = result

        resolved_documents: set[object] = set()

        for match in matches:
            if match.chunk.metadata_.get("representation_type") != "summary":
                _keep_best(match)
                continue

            document_id = match.chunk.document_id
            if document_id in resolved_documents:
                continue
            resolved_documents.add(document_id)

            # Re-run the same query embedding scoped to just this
            # document, not a blind "first few chunks" grab — this is
            # what actually finds the document's genuinely most
            # relevant real chunk(s) for the query, not an arbitrary
            # excerpt. Fetches a few extra candidates and filters the
            # summary entry itself back out in Python rather than at
            # the Chroma `where` level — robust regardless of whether
            # any given chunk happens to carry a `representation_type`
            # key at all (ordinary chunks never do, by design).
            candidates = await self._vector_store.similarity_search(
                query_embedding=request.query_embedding,
                filters=replace(request.filters, document_id=document_id),
                options=SearchOptions(limit=_PRIMARY_CANDIDATES_PER_DOCUMENT),
            )

            primary_candidates = [
                candidate
                for candidate in candidates
                if candidate.chunk.metadata_.get("representation_type") != "summary"
            ]

            for candidate in primary_candidates[:_PRIMARY_RESULTS_PER_DOCUMENT]:
                _keep_best(candidate)

        return list(deduped.values())
