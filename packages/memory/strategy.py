# Memory strategy
from enum import StrEnum


class MemoryStrategy(StrEnum):
    MEMORY = "memory"
    REDIS = "redis"
    POSTGRES = "postgres"
    MONGO = "mongo"