# pipeline.py
"""
Splitter pipeline.
"""

from __future__ import annotations

from langchain_core.documents import Document

from .base import BaseSplitter


class DocumentSplitterPipeline:

    def __init__(
        self,
        splitter: BaseSplitter,
    ) -> None:

        self._splitter = splitter

    async def split(
        self,
        documents: list[Document],
    ) -> list[Document]:

        return await self._splitter.split(
            documents,
        )