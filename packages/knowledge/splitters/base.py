"""
Base document splitter.
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from langchain_core.documents import Document


class BaseSplitter(ABC):
    """
    Base contract for all document splitters.
    """

    @abstractmethod
    async def split(
        self,
        documents: list[Document],
    ) -> list[Document]:
        """
        Split documents into chunks.

        Args:
            documents: Documents to split.

        Returns:
            List of chunked documents.
        """
        raise NotImplementedError