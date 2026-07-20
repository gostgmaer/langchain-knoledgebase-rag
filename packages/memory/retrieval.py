"""
packages/memory/retrieval.py

AI Memory Retrieval

Responsible for semantic retrieval of long-term memories.

Implementations may use:
- pgvector
- Chroma
- Pinecone
- Qdrant
- Weaviate

The retriever does not know how memories are stored.
It only retrieves the most relevant memories.
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from packages.memory.schemas import (
    SearchMemoryRequest,
    SearchMemoryResponse,
)


class MemoryRetriever(ABC):
    """
    Semantic memory retrieval interface.
    """

    @abstractmethod
    async def search(
        self,
        request: SearchMemoryRequest,
    ) -> SearchMemoryResponse:
        """
        Retrieve the most relevant memories.

        Returns:
            SearchMemoryResponse
        """
        ...