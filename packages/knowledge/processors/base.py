# base.py
from __future__ import annotations

from abc import ABC, abstractmethod

from langchain_core.documents import Document


class DocumentProcessor(ABC):
    """Base contract for document processors."""

    @abstractmethod
    async def process(
        self,
        documents: list[Document],
    ) -> list[Document]:
        raise NotImplementedError