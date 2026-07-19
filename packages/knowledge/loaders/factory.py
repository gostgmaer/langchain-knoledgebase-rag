"""
Document loader factory.
"""

from __future__ import annotations

from pathlib import Path

from packages.knowledge.exceptions import UnsupportedDocumentError
from packages.knowledge.interfaces import DocumentLoader

from .csv import CSVDocumentLoader
from .docx import DocxDocumentLoader
from .html import HTMLDocumentLoader
from .json import JSONDocumentLoader
from .markdown import MarkdownDocumentLoader
from .pdf import PDFDocumentLoader
from .text import TextDocumentLoader


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
        path: Path,
    ) -> DocumentLoader:

        extension = path.suffix.lower()

        loader = cls._loaders.get(extension)

        if loader is None:
            raise UnsupportedDocumentError(extension)

        return loader()