"""
Base document loader.
"""

from __future__ import annotations

from abc import ABC
from pathlib import Path

from langchain_core.documents import Document

from packages.shared.logging import get_logger
from packages.knowledge.exceptions import (
    DocumentNotFoundError,
    DocumentReadError,
    InvalidDocumentError,
)
from packages.knowledge.interfaces import DocumentLoader


def __init__(self, logger: get_logger) -> None:
    self._logger = logger


class BaseDocumentLoader(DocumentLoader, ABC):
    """Base class for all document loaders."""

    loader_name: str = "base"

    async def load(self, path: Path) -> list[Document]:
        raise NotImplementedError

    @staticmethod
    def validate(path: Path) -> None:
        """Validate the document path."""

        if not path.exists():
            raise DocumentNotFoundError(str(path))

        if not path.is_file():
            raise InvalidDocumentError(str(path))

    def normalize_metadata(
        self,
        documents: list[Document],
        path: Path,
    ) -> list[Document]:
        """
        Normalize metadata across all loaders.
        """

        for document in documents:
            metadata = document.metadata or {}

            metadata.setdefault("source", str(path))
            metadata.setdefault("filename", path.name)
            metadata.setdefault("extension", path.suffix.lower())
            metadata.setdefault("loader", self.loader_name)

            document.metadata = metadata

        return documents

    async def execute(
        self,
        path: Path,
        loader,
    ) -> list[Document]:
        """
        Execute a LangChain loader.
        """

        self.validate(path)

        logger.info(
            "Loading document",
            loader=self.loader_name,
            path=str(path),
        )

        try:
            documents = await loader.aload()

            documents = self.normalize_metadata(
                documents,
                path,
            )

            logger.info(
                "Document loaded",
                loader=self.loader_name,
                documents=len(documents),
            )

            return documents

        except Exception as exc:
            logger.exception(
                "Failed loading document",
                loader=self.loader_name,
                path=str(path),
            )

            raise DocumentReadError(
                str(path),
                str(exc),
            ) from exc
