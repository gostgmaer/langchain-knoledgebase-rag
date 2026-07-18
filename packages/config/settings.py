from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.enums import (
    CLITheme,
    EmbeddingProvider,
    LLMProvider,
    LogFormat,
    LogLevel,
    RetrievalStrategy,
    SearchProvider,
    VectorStore,
)


class Settings(BaseSettings):
    """Application Settings"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =====================================================
    # Application
    # =====================================================

    app_name: str = Field(alias="APP_NAME")
    app_version: str = Field(alias="APP_VERSION")
    debug:bool=Field(alias="DEBUG")

    # =====================================================
    # LLM
    # =====================================================

    openai_api_key: str | None = Field(
        default=None,
        alias="OPENAI_API_KEY",
    )

    anthropic_api_key: str | None = Field(
        default=None,
        alias="ANTHROPIC_API_KEY",
    )

    google_api_key: str | None = Field(
        default=None,
        alias="GOOGLE_API_KEY",
    )

    groq_api_key: str | None = Field(
        default=None,
        alias="GROQ_API_KEY",
    )

    llm_provider: LLMProvider = Field(alias="LLM_PROVIDER")

    llm_model: str = Field(alias="LLM_MODEL")

    llm_temperature: float = Field(
        default=0.7,
        alias="LLM_TEMPERATURE",
    )

    llm_max_tokens: int = Field(
        default=2048,
        alias="LLM_MAX_TOKENS",
    )

    llm_streaming: bool = Field(
        default=True,
        alias="LLM_STREAMING",
    )

    # =====================================================
    # Embeddings
    # =====================================================

    embedding_provider: EmbeddingProvider = Field(
        alias="EMBEDDING_PROVIDER",
    )

    embedding_model: str = Field(
        alias="EMBEDDING_MODEL",
    )

    # =====================================================
    # Vector Store
    # =====================================================

    vector_store: VectorStore = Field(
        alias="VECTOR_STORE",
    )

    chroma_persist_dir: Path = Field(
        alias="CHROMA_PERSIST_DIR",
    )

    faiss_index_path: Path = Field(
        alias="FAISS_INDEX_PATH",
    )

    qdrant_url: str = Field(alias="QDRANT_URL")

    qdrant_api_key: str | None = Field(
        default=None,
        alias="QDRANT_API_KEY",
    )

    # =====================================================
    # Database
    # =====================================================

    postgres_host: str = Field(alias="POSTGRES_HOST")
    postgres_port: int = Field(alias="POSTGRES_PORT")
    postgres_db: str = Field(alias="POSTGRES_DB")
    postgres_user: str = Field(alias="POSTGRES_USER")
    postgres_password: str = Field(alias="POSTGRES_PASSWORD")

    database_url: str = Field(alias="DATABASE_URL")

    sqlite_checkpoint_db: Path = Field(alias="CHECKPOINT_DB_PATH")
    sqlite_session_db: Path = Field(alias="SESSION_DB_PATH")
    sqlite_summary_db: Path = Field(alias="SUMMARY_DB_PATH")

    # =====================================================
    # Memory
    # =====================================================

    max_history_messages: int = Field(
        alias="MAX_HISTORY_MESSAGES",
    )

    summarize_after_n_messages: int = Field(
        alias="SUMMARY_TRIGGER_MESSAGES",
    )

    # =====================================================
    # Tools
    # =====================================================

    weather_api_key: str | None = Field(
        default=None,
        alias="OPENWEATHER_API_KEY",
    )

    weather_api_url: str = Field(alias="OPENWEATHER_BASE_URL")

    news_api_key: str | None = Field(
        default=None,
        alias="NEWS_API_KEY",
    )

    news_api_url: str = Field(alias="NEWSAPI_BASE_URL")

    search_provider: SearchProvider = Field(
        alias="SEARCH_PROVIDER",
    )

    serper_api_key: str | None = Field(
        default=None,
        alias="SERPER_API_KEY",
    )

    tavily_api_key: str | None = Field(
        default=None,
        alias="TAVILY_API_KEY",
    )

    # =====================================================
    # RAG
    # =====================================================

    upload_dir: Path = Field(alias="UPLOAD_DIR")

    chunk_size: int = Field(alias="CHUNK_SIZE")

    chunk_overlap: int = Field(alias="CHUNK_OVERLAP")

    retrieval_top_k: int = Field(alias="RETRIEVAL_TOP_K")

    retrieval_strategy: RetrievalStrategy = Field(
        alias="RETRIEVAL_STRATEGY",
    )

    # =====================================================
    # CLI
    # =====================================================

    cli_theme: CLITheme = Field(alias="CLI_THEME")

    cli_streaming: bool = Field(alias="CLI_STREAMING")

    cli_show_tool_calls: bool = Field(
        alias="CLI_SHOW_TOOL_CALLS",
    )

    cli_show_thinking: bool = Field(
        alias="CLI_SHOW_THINKING",
    )

    # =====================================================
    # Logging
    # =====================================================

    log_level: LogLevel = Field(alias="LOG_LEVEL")

    log_file: Path = Field(alias="LOG_FILE")

    log_format: LogFormat = Field(alias="LOG_FORMAT")

    # =====================================================
    # LangSmith
    # =====================================================

    langchain_tracing: bool = Field(
        alias="LANGCHAIN_TRACING_V2",
    )

    langchain_endpoint: str = Field(
        alias="LANGCHAIN_ENDPOINT",
    )

    langchain_api_key: str | None = Field(
        default=None,
        alias="LANGCHAIN_API_KEY",
    )

    langchain_project: str = Field(
        alias="LANGCHAIN_PROJECT",
    )

    # =====================================================
    # Session
    # =====================================================

    session_ttl_hours: int = Field(
        alias="SESSION_TTL_HOURS",
    )

    max_sessions: int = Field(
        alias="MAX_SESSIONS",
    )

    @field_validator("llm_temperature")
    @classmethod
    def validate_temperature(cls, value: float) -> float:
        if not 0 <= value <= 2:
            raise ValueError(
                "LLM temperature must be between 0 and 2."
            )
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()