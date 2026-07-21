# markdown.py
"""
Markdown document loader.
"""

from __future__ import annotations

from pathlib import Path

from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_core.documents import Document

from .base import BaseDocumentLoader


class MarkdownDocumentLoader(BaseDocumentLoader):

    loader_name = "markdown"

    async def load(
        self,
        path: Path,
    ) -> list[Document]:

        loader = UnstructuredMarkdownLoader(
            str(path),
        )

        return await self.execute(
            path=path,
            loader=loader,
        )