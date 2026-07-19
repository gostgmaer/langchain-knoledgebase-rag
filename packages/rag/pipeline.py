# RAG Pipeline
from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document

from packages.rag.indexer import DocumentIndexer
from packages.rag.retriever import RetrievalPipeline


class RAGPipeline:
    """Coordinates indexing and retrieval."""

    def __init__(
        self,
        indexer: DocumentIndexer,
        retriever: RetrievalPipeline,
    ) -> None:
        self.indexer = indexer
        self.retriever = retriever

    async def index(
        self,
        file_path: str | Path,
    ) -> list[Document]:
        return await self.indexer.index_file(file_path)

    async def search(
        self,
        query: str,
        *,
        k: int = 5,
    ) -> list[Document]:
        return await self.retriever.retrieve(
            query=query,
            k=k,
        )