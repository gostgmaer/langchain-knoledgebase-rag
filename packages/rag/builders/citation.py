# citation.py
"""
RAG citation builder.
"""

from __future__ import annotations

from packages.knowledge.retrievers.schemas import SearchResult
from packages.rag.schemas import Citation


class CitationBuilder:
    """
    Builds citations from retrieval results.
    """

    def build(
        self,
        search_results: list[SearchResult],
    ) -> list[Citation]:
        """
        Build citations from search results.
        """

        citations: list[Citation] = []

        for result in search_results:
            citations.append(
                Citation(
                    document_id=result.document_id,
                    chunk_id=result.chunk_id,
                    chunk_index=result.chunk_index,
                    score=result.score,
                )
            )

        return citations