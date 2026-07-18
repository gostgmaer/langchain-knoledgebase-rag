# RAG exceptions
class RAGError(Exception):
    """Base RAG exception."""


class EmbeddingError(RAGError):
    pass


class VectorStoreError(RAGError):
    pass


class RetrievalError(RAGError):
    pass