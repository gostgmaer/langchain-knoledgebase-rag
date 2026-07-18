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

    def __init__(
        self,
        embeddings: EmbeddingManager,
        vectorstore: VectorStoreManager,
        loader: DocumentLoader,
        splitter: DocumentSplitter,
        indexer: DocumentIndexer,
        retriever: RAGRetriever,
        pipeline: RAGPipeline,
    ) -> None:
        self.embeddings = embeddings
        self.vectorstore = vectorstore
        self.loader = loader
        self.splitter = splitter
        self.indexer = indexer
        self.retriever = retriever
        self.pipeline = pipeline

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