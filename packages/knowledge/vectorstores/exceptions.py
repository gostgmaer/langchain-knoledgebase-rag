"""
Vector store exceptions.
"""

from __future__ import annotations


class VectorStoreError(Exception):
    """Base vector store exception."""


class VectorStoreConnectionError(VectorStoreError):
    """Unable to connect to vector store."""


class VectorStoreConfigurationError(VectorStoreError):
    """Invalid vector store configuration."""


class VectorStoreNotFoundError(VectorStoreError):
    """Requested vector not found."""


class VectorStoreSearchError(VectorStoreError):
    """Similarity search failed."""


class VectorStoreInsertError(VectorStoreError):
    """Unable to store vectors."""


class VectorStoreDeleteError(VectorStoreError):
    """Unable to delete vectors."""