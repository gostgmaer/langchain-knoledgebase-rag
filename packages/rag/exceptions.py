class RAGException(Exception):
    """Base exception for RAG."""


class LoaderException(RAGException):
    """Raised when document loading fails."""


class SplitterException(RAGException):
    """Raised when document splitting fails."""


class EmbeddingException(RAGException):
    """Raised when embedding generation fails."""


class VectorStoreException(RAGException):
    """Raised when vector store operations fail."""


class RetrievalException(RAGException):
    """Raised when retrieval fails."""


class IndexingException(RAGException):
    """Raised when indexing fails."""