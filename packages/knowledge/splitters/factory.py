# factory.py
"""
Splitter factory — selects a chunking strategy.
"""

from __future__ import annotations

from packages.knowledge.schemas import ChunkingStrategy

from .base import BaseSplitter
from .markdown import MarkdownDocumentSplitter
from .recursive import RecursiveDocumentSplitter
from .semantic import SemanticDocumentSplitter

_MARKDOWN_EXTENSIONS = {".md", ".markdown"}


class SplitterFactory:
    """
    Selects which splitter to use for a given ingestion.

    "auto" (the default) picks the markdown splitter for .md/.markdown
    files and the recursive splitter for everything else. Any other
    value forces that specific strategy regardless of file type —
    semantic chunking in particular is opt-in, since it embeds every
    sentence and is meaningfully more expensive than the alternatives.
    """

    def __init__(
        self,
        recursive_splitter: RecursiveDocumentSplitter,
        markdown_splitter: MarkdownDocumentSplitter,
        semantic_splitter: SemanticDocumentSplitter,
    ) -> None:
        self._recursive = recursive_splitter
        self._markdown = markdown_splitter
        self._semantic = semantic_splitter

    @staticmethod
    def resolve(
        *,
        strategy: ChunkingStrategy = "auto",
        file_extension: str = "",
    ) -> ChunkingStrategy:
        """
        The strategy that will actually run: what "auto" turns into for this file type,
        or the explicit choice unchanged. Recorded on the document and on every chunk so
        the UI can show which method produced them.
        """
        if strategy != "auto":
            return strategy

        if file_extension.lower() in _MARKDOWN_EXTENSIONS:
            return "markdown"

        return "recursive"

    def create(
        self,
        *,
        strategy: ChunkingStrategy = "auto",
        file_extension: str = "",
    ) -> BaseSplitter:

        effective = self.resolve(strategy=strategy, file_extension=file_extension)

        if effective == "markdown":
            return self._markdown

        if effective == "semantic":
            return self._semantic

        return self._recursive
