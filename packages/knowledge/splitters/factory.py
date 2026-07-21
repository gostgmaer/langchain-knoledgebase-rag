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

    def create(
        self,
        *,
        strategy: ChunkingStrategy = "auto",
        file_extension: str = "",
    ) -> BaseSplitter:

        if strategy == "recursive":
            return self._recursive

        if strategy == "markdown":
            return self._markdown

        if strategy == "semantic":
            return self._semantic

        # "auto"
        if file_extension.lower() in _MARKDOWN_EXTENSIONS:
            return self._markdown

        return self._recursive
