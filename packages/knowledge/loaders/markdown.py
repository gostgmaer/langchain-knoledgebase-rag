# markdown.py
"""
Markdown document loader.
"""

from __future__ import annotations

from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document

from .base import BaseDocumentLoader


class MarkdownDocumentLoader(BaseDocumentLoader):
    """
    Loads a .md file as raw text, not via `UnstructuredMarkdownLoader`
    — that pulls in the `unstructured` package (pruned from this
    project's lockfile as an unused dependency, confirmed live: it's
    missing and this loader crashes on import) and, independent of
    that, reformats markdown into parsed "elements" that strip the
    literal `#`/`##`/`###` header syntax `MarkdownDocumentSplitter`
    (packages/knowledge/splitters/markdown.py, which uses
    `MarkdownHeaderTextSplitter`) needs intact to find section
    boundaries at all. Loading as plain text preserves exactly what
    the splitter downstream actually depends on.
    """

    loader_name = "markdown"

    async def load(
        self,
        path: Path,
    ) -> list[Document]:

        loader = TextLoader(
            file_path=str(path),
            encoding="utf-8",
        )

        return await self.execute(
            path=path,
            loader=loader,
        )