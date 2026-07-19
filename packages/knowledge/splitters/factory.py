# factory.py
"""
Splitter factory.
"""

from __future__ import annotations

from .recursive import RecursiveDocumentSplitter


class SplitterFactory:

    @staticmethod
    def create() -> RecursiveDocumentSplitter:
        return RecursiveDocumentSplitter()