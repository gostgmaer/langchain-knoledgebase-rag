"""
Base document splitter.
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from packages.knowledge.splitters.schema import SplitRequest
from packages.domain.models.document_chunk import DocumentChunk


class BaseSplitter(ABC):
    """
    Base contract for all document splitters.
    """

    @abstractmethod
    async def split(
        self,
        request: SplitRequest,
    ) -> list[DocumentChunk]:
        """
        Split a document into chunks.

        Args:
            request: Split request.

        Returns:
            List of document chunks.
        """
        raise NotImplementedError