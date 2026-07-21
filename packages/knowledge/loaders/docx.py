# docx.py
"""
DOCX document loader.
"""

from __future__ import annotations

from pathlib import Path

import docx
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

        documents = await self.execute(
            path=path,
            loader=loader,
        )

        self._attach_core_properties(documents, path)

        return documents

    @staticmethod
    def _attach_core_properties(
        documents: list[Document],
        path: Path,
    ) -> None:
        """
        Docx2txtLoader only extracts text, not document properties —
        pull author/title from the file's own core properties where
        present, skipped silently otherwise.
        """

        try:
            properties = docx.Document(str(path)).core_properties
        except Exception:
            return

        for document in documents:
            if properties.author:
                document.metadata.setdefault("author", properties.author)
            if properties.title:
                document.metadata.setdefault("title", properties.title)