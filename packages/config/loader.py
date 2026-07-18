from functools import lru_cache

from packages.config.upload_service import UploadServiceSettings

from .ai import AISettings
from .api import APISettings
from .app import AppSettings
from .database import DatabaseSettings
from .features import FeatureSettings
from .logging import LoggingSettings
from .queue import QueueSettings
from .redis import RedisSettings
from .security import SecuritySettings
from .settings import Settings
from .storage import StorageSettings
from .iam import IAMSettings


@lru_cache
def get_settings() -> Settings:
    return Settings(
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
        iam = IAMSettings()
    )