# retrieval.py
"""
RAG retrieval pipeline.
"""

from __future__ import annotations

import uuid
from packages.rag.vectorstore import VectorStoreManager
from packages.knowledge.retrievers.schemas import SearchResult
from packages.knowledge.vectorstores.schema import SearchFilter
from packages.rag.schemas import RAGRequest


class RetrievalPipeline:
    """
    Executes the retrieval stage of the RAG pipeline.
    """

    def __init__(
        self,
        vectorstore: VectorStoreManager,
    ) -> None:
        self._vectorstore = vectorstore

    async def retrieve(
        self,
        request: RAGRequest,
    ) -> list[SearchResult]:
        """
        Retrieve relevant knowledge for a user query.
        """

        documents = await self._vectorstore.similarity_search(
            query=request.query,
            k=5,
        )

        results = []
        for index, doc in enumerate(documents):
            results.append(
                SearchResult(
                    document_id=uuid.uuid4(),
                    chunk_id=uuid.uuid4(),
                    chunk_index=index,
                    content=doc.page_content,
                    score=1.0,
                    metadata=doc.metadata,
                )
            )

        return results