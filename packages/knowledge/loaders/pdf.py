"""
PDF document loader.
"""

from __future__ import annotations

from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

from .base import BaseDocumentLoader


class PDFDocumentLoader(BaseDocumentLoader):
    """Loads PDF documents using LangChain."""

    loader_name = "pdf"

    async def load(
        self,
        path: Path,
    ) -> list[Document]:

        loader = PyPDFLoader(
            file_path=str(path),
        )

        return await self.execute(
            path=path,
            loader=loader,
        )