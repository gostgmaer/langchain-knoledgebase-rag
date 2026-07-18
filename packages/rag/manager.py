# RAG manager
from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document

from packages.rag.embeddings import EmbeddingManager
from packages.rag.indexer import DocumentIndexer
from packages.rag.loader import DocumentLoader
from packages.rag.pipeline import RAGPipeline
from packages.rag.retriever import RAGRetriever
from packages.rag.splitter import DocumentSplitter
from packages.rag.vectorstore import VectorStoreManager


class RAGManager:
    """Facade for the complete RAG subsystem."""

    def __init__(self) -> None:
        self.embeddings = EmbeddingManager()

        self.vectorstore = VectorStoreManager(
            self.embeddings,
        )

        self.loader = DocumentLoader()

        self.splitter = DocumentSplitter()

        self.indexer = DocumentIndexer(
            loader=self.loader,
            splitter=self.splitter,
            embeddings=self.embeddings,
            vectorstore=self.vectorstore,
        )

        self.retriever = RAGRetriever(
            self.vectorstore,
        )

        self.pipeline = RAGPipeline(
            self.indexer,
            self.retriever,
        )

    async def index(
        self,
        file_path: str | Path,
    ) -> list[Document]:
        return await self.pipeline.index(file_path)

    async def retrieve(
        self,
        query: str,
        *,
        k: int = 5,
    ) -> list[Document]:
        return await self.pipeline.search(
            query=query,
            k=k,
        )

    def get_retriever(self):
        return self.retriever.as_retriever()