from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings

from packages.config.embedding import EmbeddingSettings
from .ai import AISettings
from .api import APISettings
from .app import AppSettings
from .database import DatabaseSettings
from .features import FeatureSettings
from .logging import LoggingSettings
from .queue import QueueSettings
from .redis import RedisSettings
from .security import SecuritySettings
from .storage import StorageSettings
from .upload_service import UploadServiceSettings
from .iam import IAMSettings
from .rag import RAGSettings


class Settings(BaseSettings):
    app: AppSettings = Field(default_factory=AppSettings)
    api: APISettings = Field(default_factory=APISettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    ai: AISettings = Field(default_factory=AISettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    queue: QueueSettings = Field(default_factory=QueueSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    features: FeatureSettings = Field(default_factory=FeatureSettings)
    upload_service: UploadServiceSettings = Field(default_factory=UploadServiceSettings)
    iam: IAMSettings = Field(default_factory=IAMSettings)
    rag: RAGSettings = Field(default_factory=RAGSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
