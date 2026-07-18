from __future__ import annotations

from enum import StrEnum


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"

    @property
    def is_development(self) -> bool:
        return self == Environment.DEVELOPMENT

    @property
    def is_test(self) -> bool:
        return self == Environment.TEST

    @property
    def is_staging(self) -> bool:
        return self == Environment.STAGING

    @property
    def is_production(self) -> bool:
        return self == Environment.PRODUCTION