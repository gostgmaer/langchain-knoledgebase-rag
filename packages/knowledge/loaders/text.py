# text.py
"""
Text document loader.
"""

from __future__ import annotations

from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document

from .base import BaseDocumentLoader


class TextDocumentLoader(BaseDocumentLoader):

    loader_name = "text"

    async def load(
        self,
        path: Path,
    ) -> list[Document]:

        loader = TextLoader(
            file_path=str(path),
            encoding="utf-8",
        )

        return await self.execute(
            path=path,
            loader=loader,
        )