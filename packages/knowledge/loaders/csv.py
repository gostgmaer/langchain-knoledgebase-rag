"""
CSV document loader.
"""

from __future__ import annotations

from pathlib import Path

from langchain_community.document_loaders import CSVLoader
from langchain_core.documents import Document

from .base import BaseDocumentLoader


class CSVDocumentLoader(BaseDocumentLoader):
    """Loads CSV documents using LangChain."""

    loader_name = "csv"

    async def load(
        self,
        path: Path,
    ) -> list[Document]:

        loader = CSVLoader(
            file_path=str(path),
            encoding="utf-8",
        )

        return await self.execute(
            path=path,
            loader=loader,
        )