"""
RAG exceptions.
"""

from __future__ import annotations


class RAGError(Exception):
    """
    Base exception for the RAG package.
    """


class RetrievalError(RAGError):
    """
    Raised when retrieval fails.
    """


class ContextBuildError(RAGError):
    """
    Raised when context construction fails.
    """


class PromptBuildError(RAGError):
    """
    Raised when prompt construction fails.
    """


class CitationBuildError(RAGError):
    """
    Raised when citation generation fails.
    """


class ResponseGenerationError(RAGError):
    """
    Raised when the language model fails to generate a response.
    """
class EmbeddingException(RAGError):
    """
    Raised when embedding generation fails.
    """
class LoaderException(RAGError):
    """
    Raised when document loading fails.
    """
class VectorStoreException(RAGError):
    """
    Raised when vector store operations fail.
    """