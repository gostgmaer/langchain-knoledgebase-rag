# base.py
"""
Base document splitter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from langchain_core.documents import Document


class DocumentSplitter(ABC):
    """Base contract for all document splitters."""

    @abstractmethod
    async def split(
        self,
        documents: list[Document],
    ) -> list[Document]:
        raise NotImplementedError