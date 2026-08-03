# parent_document.py
from __future__ import annotations

from dataclasses import replace

from packages.domain.models.document_chunk import DocumentChunk
from packages.knowledge.retrievers.base import BaseRetriever
from packages.knowledge.retrievers.schemas import RetrievalRequest
from packages.knowledge.vectorstores.manager import VectorStoreManager
from packages.knowledge.vectorstores.schema import SearchResult


class ParentDocumentRetriever(BaseRetriever):
    """
    Retrieves small chunks for match precision, then returns their
    full parent section for answer context (docs/mvpRAG.md v2.0) —
    reassembled from same-`(document_id, section)` sibling chunks via
    `list_chunks()`, not a separately stored parent blob. No reopening
    Document Processing (Phase 8)'s "chunk content stays vector-store-
    only" decision: the parent is built from chunks that already live
    there.

    A chunk with no `section` (plain-text documents with no markdown
    headers to group by) is returned unchanged — deliberately not
    expanded to the whole document, which could be arbitrarily large
    and blow the context budget uncontrolled.
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

        results: list[SearchResult] = []
        seen_parents: set[tuple[object, str]] = set()

        for match in matches:
            section = match.chunk.section

            if section is None:
                results.append(match)
                continue

            parent_key = (match.chunk.document_id, section)
            if parent_key in seen_parents:
                continue
            seen_parents.add(parent_key)

            siblings = await self._vector_store.list_chunks(
                filters=replace(
                    request.filters,
                    document_id=match.chunk.document_id,
                    metadata={**request.filters.metadata, "section": section},
                ),
            )

            if not siblings:
                results.append(match)
                continue

            siblings.sort(key=lambda sibling: sibling.chunk.chunk_index)

            parent_content = "\n\n".join(sibling.chunk.content for sibling in siblings)

            # DocumentChunk is a SQLAlchemy declarative model, not a
            # dataclass — dataclasses.replace() doesn't apply. These
            # instances are freshly built from a Chroma result each
            # call (ChromaVectorStore.similarity_search()/list_chunks())
            # and never session-attached, so constructing a fresh one
            # with the matched chunk's own identity/citation fields but
            # the reassembled parent content is safe — no risk of an
            # accidental ORM flush/persist.
            parent_chunk = DocumentChunk(
                id=match.chunk.id,
                tenant_id=match.chunk.tenant_id,
                document_id=match.chunk.document_id,
                chunk_index=match.chunk.chunk_index,
                section=match.chunk.section,
                page_number=match.chunk.page_number,
                content=parent_content,
                token_count=match.chunk.token_count,
                character_count=len(parent_content),
                metadata_=match.chunk.metadata_,
            )

            results.append(
                SearchResult(
                    chunk=parent_chunk,
                    score=match.score,
                )
            )

        return results
