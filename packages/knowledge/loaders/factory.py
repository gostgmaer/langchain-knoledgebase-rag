"""
Document loader factory.
"""

from __future__ import annotations

from pathlib import Path

from packages.knowledge.exceptions import UnsupportedDocumentError
from packages.knowledge.interfaces import DocumentLoader

from packages.knowledge.loaders.csv import CSVDocumentLoader
from packages.knowledge.loaders.docx import DocxDocumentLoader
from packages.knowledge.loaders.html import HTMLDocumentLoader
from packages.knowledge.loaders.json import JSONDocumentLoader
from packages.knowledge.loaders.markdown import MarkdownDocumentLoader
from packages.knowledge.loaders.pdf import PDFDocumentLoader
from packages.knowledge.loaders.text import TextDocumentLoader


class LoaderFactory:
    """Factory responsible for creating document loaders."""

    _loaders: dict[str, type[DocumentLoader]] = {
        ".pdf": PDFDocumentLoader,
        ".docx": DocxDocumentLoader,
        ".txt": TextDocumentLoader,
        ".md": MarkdownDocumentLoader,
        ".markdown": MarkdownDocumentLoader,
        ".html": HTMLDocumentLoader,
        ".htm": HTMLDocumentLoader,
        ".csv": CSVDocumentLoader,
        ".json": JSONDocumentLoader,
    }

    @classmethod
    def create(
        cls,
        path: str | Path,
    ) -> DocumentLoader:

        extension = Path(path).suffix.lower()

        loader = cls._loaders.get(extension)

        if loader is None:
            raise UnsupportedDocumentError(extension)

        return loader()