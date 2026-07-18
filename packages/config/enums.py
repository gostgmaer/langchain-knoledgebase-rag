from __future__ import annotations
from enum import StrEnum
"""
Application-wide enumerations.

This module contains all enums shared across the project.
Using enums instead of raw strings improves type safety,
autocomplete support, validation, and maintainability.
"""




class AppEnvironment(StrEnum):
    """Application environment."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class LLMProvider(StrEnum):
    """Supported Large Language Model providers."""

    GOOGLE = "google"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"


class EmbeddingProvider(StrEnum):
    """Supported embedding providers."""

    GOOGLE = "google"
    OPENAI = "openai"
    HUGGINGFACE = "huggingface"


class VectorStore(StrEnum):
    """Supported vector databases."""

    CHROMA = "chroma"
    FAISS = "faiss"
    PGVECTOR = "pgvector"
    QDRANT = "qdrant"


class SearchProvider(StrEnum):
    """Supported web search providers."""

    SERPER = "serper"
    TAVILY = "tavily"
    DUCKDUCKGO = "duckduckgo"


class RetrievalStrategy(StrEnum):
    """Supported retrieval strategies."""

    SIMILARITY = "similarity"
    MMR = "mmr"
    HYBRID = "hybrid"


class CLITheme(StrEnum):
    """Supported CLI themes."""

    DARK = "dark"
    LIGHT = "light"


class LogLevel(StrEnum):
    """Logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(StrEnum):
    """Supported logger output formats."""

    RICH = "rich"
    JSON = "json"
    PLAIN = "plain"

class StorageProvider(StrEnum):
    LOCAL = "local"
    S3 = "s3"
    AZURE = "azure"
    MINIO = "minio"