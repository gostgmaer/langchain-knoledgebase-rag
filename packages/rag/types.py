# RAG types
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore

Documents = list[Document]

EmbeddingModel = Embeddings

VectorDatabase = VectorStore