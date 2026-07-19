# exceptions.py
"""
Knowledge module exceptions.
"""

from __future__ import annotations


class KnowledgeError(Exception):
    """Base exception for the knowledge module."""


class LoaderError(KnowledgeError):
    """Base exception raised by document loaders."""


class UnsupportedDocumentError(LoaderError):
    """Raised when no loader exists for a document type."""

    def __init__(self, extension: str) -> None:
        super().__init__(f"Unsupported document type: '{extension}'")
        self.extension = extension


class DocumentNotFoundError(LoaderError):
    """Raised when the document cannot be found."""

    def __init__(self, path: str) -> None:
        super().__init__(f"Document not found: '{path}'")
        self.path = path


class InvalidDocumentError(LoaderError):
    """Raised when the supplied path is not a valid document."""

    def __init__(self, path: str) -> None:
        super().__init__(f"Invalid document: '{path}'")
        self.path = path


class DocumentReadError(LoaderError):
    """Raised when a document cannot be loaded."""

    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"Failed to read document '{path}'. {reason}")
        self.path = path