# markdown.py
"""
Markdown document loader.
"""

from __future__ import annotations

from pathlib import Path

from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_core.documents import Document

from packages.shared.logging import get_logger
from .base import BaseDocumentLoader
logger = get_logger(__name__)

class MarkdownLoader(BaseDocumentLoader):

    loader_name = "markdown"

    def __init__(self, logger: get_logger) -> None:
        super().__init__(logger)

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