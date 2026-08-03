# self_query.py
from __future__ import annotations

from dataclasses import replace

from pydantic import BaseModel, Field

from packages.infrastructure.ai.manager import LLMManager
from packages.knowledge.retrievers.base import BaseRetriever
from packages.knowledge.retrievers.schemas import RetrievalRequest
from packages.knowledge.vectorstores.schema import SearchResult
from packages.shared.logging import get_logger

logger = get_logger(__name__)


class SelfQueryFilters(BaseModel):
    """
    One structured-output LLM call translating a natural-language
    query into the metadata filters `SearchFilter.metadata`
    (packages/knowledge/vectorstores/schema.py) already supports end
    to end — restricted to the two fields real ingested chunks
    actually carry (packages/domain/models/document_chunk.py's
    `section`/`page_number`, propagated into Chroma's stored metadata
    by ChromaVectorStore.add()). Don't invent a schema the data can't
    back: most chunk metadata still lives in an untyped JSONB blob
    with no fixed keys to filter on.
    """

    section: str | None = Field(
        default=None,
        description=(
            "The document section/heading the user is asking about, "
            "if they named or clearly implied one (e.g. 'introduction', "
            "'specifications'). Omit if the query doesn't reference a "
            "specific section."
        ),
    )

    page_number: int | None = Field(
        default=None,
        description=(
            "The specific page number the user asked about, if any. "
            "Omit unless a page number is explicitly stated."
        ),
    )


class SelfQueryRetriever(BaseRetriever):
    """
    Wraps an inner retriever (whichever strategy is otherwise
    configured — hybrid by default) with an LLM step that extracts
    real, filterable metadata from the query before delegating —
    composition, not a replacement search algorithm, so self-query
    filtering layers on top of whatever ranking the inner retriever
    already does.

    Fails open on any LLM error, same idiom as GraphPlanner's
    fallback-to-keyword-matching (packages/planner/planner.py) — a
    classifier hiccup should never crash a turn, just search with
    whatever filters were already present.
    """

    def __init__(
        self,
        inner: BaseRetriever,
        llm: LLMManager,
    ) -> None:
        self._inner = inner
        self._chain = llm.with_structured_output(SelfQueryFilters)

    async def retrieve(
        self,
        request: RetrievalRequest,
    ) -> list[SearchResult]:

        if not request.query.strip():
            return await self._inner.retrieve(request)

        try:
            extracted = await self._chain.ainvoke(
                "Extract any specific document section or page number "
                "the following question is asking about. Leave a field "
                "unset if the question doesn't reference one.\n\n"
                f"Question: {request.query}"
            )
        except Exception as exc:
            logger.warning(
                "Self-query filter extraction failed, searching without extra filters",
                error=str(exc),
            )
            return await self._inner.retrieve(request)

        extra_filters: dict[str, object] = {}
        if extracted.section:
            # `section_lower`, not `section` — Chroma's `where` equality
            # is exact-match/case-sensitive, and this value comes from
            # free-form LLM extraction of natural language (e.g. a user
            # asking about "specifications", lowercase), not the real
            # stored heading's original casing ("Specifications").
            # ChromaVectorStore.add() writes both; the lowercase shadow
            # field is specifically for this comparison.
            extra_filters["section_lower"] = extracted.section.lower()
        if extracted.page_number is not None:
            extra_filters["page_number"] = extracted.page_number

        if not extra_filters:
            return await self._inner.retrieve(request)

        filtered_request = replace(
            request,
            filters=replace(
                request.filters,
                metadata={**request.filters.metadata, **extra_filters},
            ),
        )

        return await self._inner.retrieve(filtered_request)
