from functools import lru_cache

from packages.config.embedding import EmbeddingSettings
from packages.config.observability import ObservabilitySettings, configure_langsmith
from packages.config.rag import RAGSettings
from packages.config.tools import ToolsSettings
from packages.config.upload_service import UploadServiceSettings

from .ai import AISettings
from .api import APISettings
from .app import AppSettings
from .database import DatabaseSettings
from .features import FeatureSettings
from .iam import IAMSettings
from .logging import LoggingSettings
from .queue import QueueSettings
from .redis import RedisSettings
from .security import SecuritySettings
from .settings import Settings
from .storage import StorageSettings


@lru_cache
def get_settings() -> Settings:
    resolved = Settings(
        app=AppSettings(),
        api=APISettings(),
        database=DatabaseSettings(),
        redis=RedisSettings(),
        ai=AISettings(),
        logging=LoggingSettings(),
        security=SecuritySettings(),
        queue=QueueSettings(),
        storage=StorageSettings(),
        features=FeatureSettings(),
        upload_service=UploadServiceSettings(),
        iam = IAMSettings(),
        rag=RAGSettings(),
        embedding=EmbeddingSettings(),
        tools=ToolsSettings(),
        observability=ObservabilitySettings(),
        )

    # Bridges observability config into real env vars before any
    # LangChain/LangGraph call can run — see configure_langsmith()'s
    # docstring for why this can't just live on the settings object.
    configure_langsmith(resolved.observability)

    return resolved

settings = get_settings()