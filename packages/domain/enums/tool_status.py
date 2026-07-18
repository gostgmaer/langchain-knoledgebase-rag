from enum import StrEnum


class ToolStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"