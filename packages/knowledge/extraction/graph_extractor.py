# Knowledge graph entity/relationship extraction
from __future__ import annotations

from langchain_core.documents import Document as LangChainDocument
from pydantic import BaseModel, Field

from packages.infrastructure.ai.manager import LLMManager
from packages.shared.logging import get_logger

logger = get_logger(__name__)

# Same bound as IngestionPipeline's _SUMMARY_SOURCE_CHAR_LIMIT — one
# extraction call per *document*, not scaling with chunk count, the
# same cost-bounding precedent Multi Vector Retriever established.
_GRAPH_SOURCE_CHAR_LIMIT = 8000


class ExtractedEntity(BaseModel):
    name: str = Field(description="The entity's name, as it appears in the text.")
    entity_type: str | None = Field(
        default=None,
        description="e.g. person, organization, product, concept, location — open-ended, no fixed set.",
    )
    description: str | None = Field(default=None)


class ExtractedRelationship(BaseModel):
    source: str = Field(description="Must exactly match a `name` from the entities list.")
    target: str = Field(description="Must exactly match a `name` from the entities list.")
    relationship_type: str = Field(description="A short verb phrase, e.g. 'works_for', 'part_of', 'related_to'.")
    description: str | None = Field(default=None)


class GraphExtraction(BaseModel):
    entities: list[ExtractedEntity] = Field(default_factory=list, max_length=15)
    relationships: list[ExtractedRelationship] = Field(default_factory=list, max_length=15)


class GraphExtractor:
    """
    One structured-output LLM call per document, extracting the key
    entities and the relationships between them — the same
    `with_structured_output()` idiom SelfQueryRetriever/QueryAnalyzer
    already use.

    Fails open *inside* `extract()` itself (unlike SelfQueryRetriever,
    which fails open at its call site) — IngestionPipeline just needs a
    uniform "empty extraction means skip" result, not a second
    exception path to handle on top of its own non-fatal wrapping.
    """

    def __init__(self, llm: LLMManager) -> None:
        self._chain = llm.with_structured_output(GraphExtraction)

    async def extract(
        self,
        chunked_documents: list[LangChainDocument],
    ) -> GraphExtraction:

        if not chunked_documents:
            return GraphExtraction()

        excerpt = ""
        for chunk in chunked_documents:
            if len(excerpt) >= _GRAPH_SOURCE_CHAR_LIMIT:
                break
            excerpt += chunk.page_content + "\n\n"
        excerpt = excerpt[:_GRAPH_SOURCE_CHAR_LIMIT]

        try:
            return await self._chain.ainvoke(
                "Extract the key entities and the relationships between "
                "them from the following document excerpt. Only extract "
                "relationships between entities you've also listed. "
                "Return only what's clearly stated in the text.\n\n"
                f"{excerpt}"
            )
        except Exception as exc:
            logger.warning(
                "Graph extraction failed, skipping graph representation for this document",
                error=str(exc),
            )
            return GraphExtraction()
