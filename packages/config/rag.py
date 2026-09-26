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

    # Chroma's embedded PersistentClient is single-process only — opening
    # it independently from both the API server and the arq worker (two
    # real OS processes, both touching the same on-disk directory) causes
    # intermittent HNSW query corruption under concurrent access
    # ("Error executing plan: Internal error: Error finding id"), not a
    # permanently broken index — a query that fails on one process can
    # succeed a moment later on another. Setting both of these switches to
    # a real `chroma run` server instead, which both processes then talk
    # to over HTTP — the one process that actually owns the on-disk data.
    # Left unset (the default) preserves the original embedded-client
    # behavior for anyone not running that server.
    chroma_server_host: str | None = Field(default=None, alias="CHROMA_SERVER_HOST")
    chroma_server_port: int | None = Field(default=None, alias="CHROMA_SERVER_PORT")

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
    # Weight of the BM25 keyword ranking relative to the dense ranking when the hybrid retriever fuses
    # them (1.0 = equal). Lower it if keyword matches on common words outrank the right document; measure
    # with scripts/evaluate_retrieval.py before changing it.
    keyword_weight: float = Field(default=1.0, ge=0.0, le=2.0, alias="RETRIEVAL_KEYWORD_WEIGHT")
    max_results: int = Field(default=5, alias="RAG_MAX_RESULTS")
    context_token_budget: int = Field(default=4000, alias="RAG_CONTEXT_TOKEN_BUDGET")
    min_relevance_score: float = Field(default=0.0, alias="RAG_MIN_RELEVANCE_SCORE")

    # Self-imposed cap on outgoing embedding calls, kept under whatever the
    # provider enforces server-side (Gemini's free tier is 100 requests/min)
    # so a backlog of queued ingestion jobs runs out of *our own* budget
    # with a clean wait instead of a 429 from the provider.
    embedding_rate_limit_requests_per_minute: int = Field(
        default=90, alias="EMBEDDING_RATE_LIMIT_REQUESTS_PER_MINUTE"
    )
    embedding_rate_limit_tokens_per_minute: int = Field(
        default=30_000, alias="EMBEDDING_RATE_LIMIT_TOKENS_PER_MINUTE"
    )

    # Scheduled Re-indexing (docs/mvpRAG.md v1.1) — a current document
    # not re-embedded in this many days becomes a candidate for the
    # weekly reindex_stale_documents_job.
    reindex_stale_after_days: int = Field(default=90, alias="REINDEX_STALE_AFTER_DAYS")

    # Data retention. Retrieval logs and audit events are deleted once older than this;
    # 0 disables the purge for that table (keep forever).
    retention_retrieval_log_days: int = Field(default=90, alias="RETENTION_RETRIEVAL_LOG_DAYS")
    retention_audit_days: int = Field(default=365, alias="RETENTION_AUDIT_DAYS")

    # External knowledge sources (connectors).
    # Fernet key(s), comma separated. The first encrypts, all decrypt (rotation). No key = credentials cannot be stored.
    connector_credential_keys: str | None = Field(default=None, alias="CONNECTOR_CREDENTIAL_KEYS")
    # Let connectors call private-network addresses (self-hosted Confluence, an intranet site). OFF by default:
    # it is the switch that stops a source URL from reaching the platform's own network.
    connector_allow_private_hosts: bool = Field(default=False, alias="CONNECTOR_ALLOW_PRIVATE_HOSTS")
    connector_sync_concurrency: int = Field(default=4, ge=1, le=16, alias="CONNECTOR_SYNC_CONCURRENCY")
    connector_max_error_details: int = Field(default=100, alias="CONNECTOR_MAX_ERROR_DETAILS")
