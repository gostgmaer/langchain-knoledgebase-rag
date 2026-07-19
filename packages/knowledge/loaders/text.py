# text.py
"""
Text document loader.
"""

from __future__ import annotations

from logging import Logger
from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document

from packages.shared.logging import get_logger
from .base import BaseDocumentLoader


class TextDocumentLoader(BaseDocumentLoader):

    loader_name = "text"

    def __init__(self, logger: get_logger) -> None:
        super().__init__(logger)

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