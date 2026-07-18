# RAG types
from __future__ import annotations

from typing import TypeAlias
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore

VectorDatabase = VectorStore
Chunk: TypeAlias = Document
Documents: TypeAlias = list[Document]
Embeddings: TypeAlias = list[list[float]]
Embedding: TypeAlias = list[float]
Metadata: TypeAlias = dict[str, object]