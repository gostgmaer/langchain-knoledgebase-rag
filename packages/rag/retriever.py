# Retriever
from __future__ import annotations

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from packages.rag.vectorstore import VectorStoreManager


class RAGRetriever:
    """High-level retrieval wrapper."""

    def __init__(
        self,
        vectorstore: VectorStoreManager,
    ) -> None:
        self.vectorstore = vectorstore

    async def retrieve(
        self,
        query: str,
        *,
        k: int = 5,
    ) -> list[Document]:
        return await self.vectorstore.similarity_search(
            query=query,
            k=k,
        )

    def as_retriever(
        self,
        *,
        k: int = 5,
    ) -> BaseRetriever:
        return self.vectorstore.client.as_retriever(
            search_kwargs={"k": k},
        )