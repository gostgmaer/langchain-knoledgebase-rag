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
    # pgvector is the real default (reuses the Postgres this app already runs; no separate server
    # needed) -- testing and production always use it. Chroma is available for local development
    # only (opt in via .env), and its own embedded-client concurrency caveat below is exactly why
    # it isn't the default anywhere it matters.
    vector_store_backend: str = Field(default="pgvector", alias="VECTOR_STORE_BACKEND")
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
    # retrieval_keyword_weight and context_token_budget moved to Platform Settings
    # (docs/BUGS.md item 38 follow-up) — see platform_settings_service.py's SETTINGS.
    max_results: int = Field(default=5, alias="RAG_MAX_RESULTS")
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

    # reindex_stale_after_days / retention_retrieval_log_days / retention_audit_days moved to the
    # database (docs/BUGS.md item 38) — admin-configurable Platform Settings now, not env vars;
    # see packages/application/services/platform_settings_service.py's SETTINGS registry for
    # their built-in defaults, and packages/worker/jobs.py / retention_service.py for how they're
    # read per run.

    # External knowledge sources (connectors).
    # Fernet key(s), comma separated. The first encrypts, all decrypt (rotation). No key = credentials cannot be stored.
    connector_credential_keys: str | None = Field(default=None, alias="CONNECTOR_CREDENTIAL_KEYS")
    # Let connectors call private-network addresses (self-hosted Confluence, an intranet site). OFF by default:
    # it is the switch that stops a source URL from reaching the platform's own network.
    connector_allow_private_hosts: bool = Field(default=False, alias="CONNECTOR_ALLOW_PRIVATE_HOSTS")
    # Optional headless-browser service for JavaScript-rendered pages (Browserless-compatible: POST {url}/content).
    # It must be network-isolated (pages it loads can request anything); unset = JavaScript rendering unavailable.
    connector_render_url: str | None = Field(default=None, alias="CONNECTOR_RENDER_URL")
    connector_render_token: str | None = Field(default=None, alias="CONNECTOR_RENDER_TOKEN")
    # connector_sync_concurrency moved to the database (docs/BUGS.md item 38) — see
    # platform_settings_service.py's SETTINGS registry and packages/connectors/sync.py.
    connector_max_error_details: int = Field(default=100, alias="CONNECTOR_MAX_ERROR_DETAILS")
