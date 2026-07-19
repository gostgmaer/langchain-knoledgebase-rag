"""
Knowledge module interfaces.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from typing import Protocol
from langchain_core.documents import Document


class DocumentLoader(Protocol):
    """Contract implemented by all document loaders."""

    @abstractmethod
    async def load(self, path: Path) -> list[Document]:
        """
        Load a document into LangChain Documents.
        """
        raise NotImplementedError