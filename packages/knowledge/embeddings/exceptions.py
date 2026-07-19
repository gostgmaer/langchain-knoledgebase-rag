"""
Embedding exceptions.
"""


class EmbeddingError(Exception):
    """Base embedding exception."""


class UnsupportedEmbeddingProviderError(EmbeddingError):
    """Unsupported provider."""


class EmbeddingGenerationError(EmbeddingError):
    """Embedding generation failed."""