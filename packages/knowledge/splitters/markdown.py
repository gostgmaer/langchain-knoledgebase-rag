# markdown.py
"""
Markdown-aware document splitter.
"""

from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from packages.config.loader import settings

from .base import BaseSplitter

_HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]


class MarkdownDocumentSplitter(BaseSplitter):
    """
    Two-stage splitter: split along Markdown header structure first
    (so chunks respect document sections, attaching the section
    heading as h1/h2/h3 metadata), then cap any oversized section
    with a regular recursive character split.
    """

    def __init__(self) -> None:

        self._header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=_HEADERS_TO_SPLIT_ON,
        )

        self._size_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.rag.chunk_size,
            chunk_overlap=settings.rag.chunk_overlap,
            separators=settings.rag.chunk_separators,
        )

    async def split(
        self,
        documents: list[Document],
    ) -> list[Document]:

        result: list[Document] = []

        for document in documents:

            sections = self._header_splitter.split_text(
                document.page_content,
            )

            for section in sections:
                section.metadata.update(document.metadata)

            result.extend(
                self._size_splitter.split_documents(sections)
            )

        return result
