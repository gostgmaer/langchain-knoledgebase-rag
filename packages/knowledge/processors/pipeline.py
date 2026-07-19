# pipeline.py
"""
Document transformation pipeline.
"""

from __future__ import annotations

from langchain_core.documents import Document

from packages.shared.logging import get_logger

from .base import DocumentTransformer

logger = get_logger(__name__)


class DocumentTransformerPipeline:
    """Executes document transformers sequentially."""

    def __init__(
        self,
        transformers: list[DocumentTransformer],
    ) -> None:
        self._transformers = transformers

    async def transform(
        self,
        documents: list[Document],
    ) -> list[Document]:

        logger.info(
            "Running %s document transformers",
            len(self._transformers),
        )

        for transformer in self._transformers:
            documents = await transformer.transform(documents)

        logger.info(
            "Document transformation completed",
            documents=len(documents),
        )

        return documents