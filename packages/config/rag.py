from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RAGSettings(BaseSettings):
    """RAG configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    embedding_provider: str = Field(default="google", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(
        default="models/embedding-001", alias="EMBEDDING_MODEL"
    )
    vector_store_backend: str = Field(default="chroma", alias="VECTOR_STORE_BACKEND")
    vector_collection_name: str = Field(
        default="langchain", alias="VECTOR_COLLECTION_NAME"
    )
    chroma_directory: str = Field(default="./storage/chroma", alias="CHROMA_DIRECTORY")

    chunk_size: int = Field(default=1000, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, alias="CHUNK_OVERLAP")
    chunk_separators: list[str] = [
        "\n\n",
        "\n",
        ". ",
        " ",
        "",
    ]

    retrieval_strategy: str = Field(default="hybrid", alias="RETRIEVAL_STRATEGY")
    max_results: int = Field(default=5, alias="RAG_MAX_RESULTS")
    context_token_budget: int = Field(default=4000, alias="RAG_CONTEXT_TOKEN_BUDGET")
    min_relevance_score: float = Field(default=0.0, alias="RAG_MIN_RELEVANCE_SCORE")
