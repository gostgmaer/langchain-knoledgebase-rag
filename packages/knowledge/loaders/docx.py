# docx.py
"""
DOCX document loader.
"""

from __future__ import annotations

from pathlib import Path

from langchain_community.document_loaders import Docx2txtLoader
from langchain_core.documents import Document

from .base import BaseDocumentLoader


class DocxDocumentLoader(BaseDocumentLoader):

    loader_name = "docx"

    async def load(
        self,
        path: Path,
    ) -> list[Document]:

        loader = Docx2txtLoader(
            str(path),
        )

        return await self.execute(
            path=path,
            loader=loader,
        )