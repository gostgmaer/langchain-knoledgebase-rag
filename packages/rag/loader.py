# Document loader
from __future__ import annotations

from pathlib import Path

from langchain_community.document_loaders import (
    CSVLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
    UnstructuredWordDocumentLoader,
)

from packages.rag.exceptions import LoaderException
from packages.rag.types import Documents


class DocumentLoader:
    """Loads documents into LangChain Document objects."""

    LOADERS = {
        ".pdf": PyPDFLoader,
        ".txt": TextLoader,
        ".md": UnstructuredMarkdownLoader,
        ".docx": UnstructuredWordDocumentLoader,
        ".csv": CSVLoader,
    }

    def load(
        self,
        file_path: str | Path,
    ) -> Documents:
        path = Path(file_path)

        loader_cls = self.LOADERS.get(path.suffix.lower())

        if loader_cls is None:
            raise LoaderException(
                f"Unsupported file type: {path.suffix}"
            )

        loader = loader_cls(str(path))

        return loader.load()