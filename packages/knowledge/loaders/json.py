"""
JSON document loader.
"""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.documents import Document

from packages.knowledge.exceptions import DocumentReadError
from .base import BaseDocumentLoader


class JSONDocumentLoader(BaseDocumentLoader):
    """Loads JSON files into LangChain Documents."""

    loader_name = "json"

    async def load(
        self,
        path: Path,
    ) -> list[Document]:

        self.validate(path)

        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

            document = Document(
                page_content=json.dumps(
                    data,
                    indent=2,
                    ensure_ascii=False,
                ),
                metadata={},
            )

            return self.normalize_metadata(
                [document],
                path,
            )

        except Exception as exc:
            raise DocumentReadError(
                str(path),
                str(exc),
            ) from exc