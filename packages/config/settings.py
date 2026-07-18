from __future__ import annotations

from dataclasses import dataclass

from pydantic_settings import BaseSettings
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

class Settings(BaseSettings):
    # app=AppSettings(),
        # api=APISettings(),
        # database=DatabaseSettings(),
        # redis=RedisSettings(),
        ai=AISettings(),
        # logging=LoggingSettings(),
        # security=SecuritySettings(),
        # queue=QueueSettings(),
        # storage=StorageSettings(),
        # features=FeatureSettings(),
        # upload_service=UploadServiceSettings(),
        # iam = IAMSettings()