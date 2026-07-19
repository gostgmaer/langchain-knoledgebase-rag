"""
HTML document loader.
"""

from __future__ import annotations

from pathlib import Path

from langchain_community.document_loaders import BSHTMLLoader
from langchain_core.documents import Document

from packages.core.logger import Logger
from .base import BaseDocumentLoader


class HTMLLoader(BaseDocumentLoader):

    loader_name = "html"

    def __init__(self, logger: Logger) -> None:
        super().__init__(logger)

    async def load(
        self,
        path: Path,
    ) -> list[Document]:

        loader = BSHTMLLoader(
            str(path),
        )

        return await self.execute(
            path=path,
            loader=loader,
        )