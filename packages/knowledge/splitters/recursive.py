# recursive.py
"""
Recursive document splitter.
"""

from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from packages.config.loader import settings

from .base import DocumentSplitter


class RecursiveDocumentSplitter(DocumentSplitter):

    def __init__(self) -> None:

        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.rag.chunk_size,
            chunk_overlap=settings.rag.chunk_overlap,
            separators=settings.rag.chunk_separators,
        )

    async def split(
        self,
        documents: list[Document],
    ) -> list[Document]:

        return self._splitter.split_documents(
            documents,
        )