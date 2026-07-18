# RAG indexer
from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document

from packages.rag.embeddings import EmbeddingManager
from packages.rag.loader import DocumentLoader
from packages.rag.splitter import DocumentSplitter
from packages.rag.vectorstore import VectorStoreManager


class DocumentIndexer:
    """Indexes documents into the vector store."""

    def __init__(
        self,
        loader: DocumentLoader,
        splitter: DocumentSplitter,
        embeddings: EmbeddingManager,
        vectorstore: VectorStoreManager,
    ) -> None:
        self.loader = loader
        self.splitter = splitter
        self.embeddings = embeddings
        self.vectorstore = vectorstore

    async def index_file(
        self,
        file_path: str | Path,
    ) -> list[Document]:
        documents = self.loader.load(file_path)

        chunks = self.splitter.split(documents)

        await self.vectorstore.add_documents(chunks)

        return chunks
    
