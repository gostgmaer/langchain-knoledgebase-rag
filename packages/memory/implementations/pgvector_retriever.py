
"""
packages/memory/implementations/pgvector_retriever.py
"""

from __future__ import annotations

from langchain_core.embeddings import Embeddings

from packages.memory.retrieval import MemoryRetriever
from packages.memory.schemas import (
    SearchMemoryRequest,
    SearchMemoryResponse,
)


class PgVectorMemoryRetriever(MemoryRetriever):
    """
    Semantic memory retrieval using pgvector.
    """

    def __init__(
        self,
        db,
        embeddings: Embeddings,
    ) -> None:
        self._db = db
        self._embeddings = embeddings

    async def search(
        self,
        request: SearchMemoryRequest,
    ) -> SearchMemoryResponse:

        embedding = await self._embeddings.aembed_query(
            request.query
        )

        #
        # TODO:
        #
        # SELECT
        #      *,
        #      embedding <=> :embedding AS score
        # FROM ai_memories
        # WHERE tenant_id = ...
        # AND user_id = ...
        # ORDER BY embedding <=> :embedding
        # LIMIT request.top_k
        #

        #
        # Convert database rows into SearchMemoryResponse
        #

        return SearchMemoryResponse()