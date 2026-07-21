"""
HTML document loader.
"""

from __future__ import annotations

from pathlib import Path

from langchain_community.document_loaders import BSHTMLLoader
from langchain_core.documents import Document

from .base import BaseDocumentLoader


class HTMLDocumentLoader(BaseDocumentLoader):

    loader_name = "html"

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