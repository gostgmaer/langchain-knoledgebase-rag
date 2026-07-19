# context.py
"""
RAG context builder.
"""

from __future__ import annotations

from packages.knowledge.retrievers.schemas import SearchResult
from packages.rag.exceptions import ContextBuildError
from packages.rag.schemas import Context


class ContextBuilder:
    """
    Builds the context supplied to the language model.
    """

    def build(
        self,
        search_results: list[SearchResult],
    ) -> Context:
        """
        Build retrieval context from search results.
        """

        if not search_results:
            raise ContextBuildError(
                "No search results available."
            )

        sections: list[str] = []

        for index, result in enumerate(search_results, start=1):
            sections.append(
                f"[{index}]\n{result.chunk.content}"
            )

        return Context(
            text="\n\n".join(sections),
            search_results=search_results,
        )