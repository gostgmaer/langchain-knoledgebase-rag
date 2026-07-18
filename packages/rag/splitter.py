# Document splitter
from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from packages.config.loader import settings
from packages.rag.types import Documents


class DocumentSplitter:
    """Splits documents into semantic chunks."""

    def __init__(self) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=[
                "\n\n",
                "\n",
                ". ",
                " ",
                "",
            ],
        )

    def split(
        self,
        documents: Documents,
    ) -> list[Document]:
        return self._splitter.split_documents(documents)