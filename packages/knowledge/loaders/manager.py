"""
Document loader manager.
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document

from packages.shared.logging import get_logger

from .factory import LoaderFactory

logger = get_logger(__name__)


class DocumentLoaderManager:
    """Public entry point for document loading."""

    async def load(
        self,
        path: Path,
    ) -> list[Document]:

        logger.info(
            "Loading document",
            path=str(path),
        )

        loader = LoaderFactory.create(path)

        documents = await loader.load(path)

        logger.info(
            "Loaded %s documents",
            len(documents),
        )

        return documents