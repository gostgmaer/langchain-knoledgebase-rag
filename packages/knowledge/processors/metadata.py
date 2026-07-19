# metadata.py
"""
Metadata transformer.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from langchain_core.documents import Document

from .base import DocumentTransformer


class MetadataTransformer(DocumentTransformer):
    """Adds common metadata to every document."""

    async def transform(
        self,
        documents: list[Document],
    ) -> list[Document]:

        processed_at = datetime.now(UTC).isoformat()

        for document in documents:

            metadata = document.metadata or {}

            metadata.setdefault(
                "document_id",
                str(uuid.uuid4()),
            )

            metadata.setdefault(
                "processed_at",
                processed_at,
            )

            metadata.setdefault(
                "version",
                1,
            )

            metadata.setdefault(
                "processed",
                True,
            )

            document.metadata = metadata

        return documents