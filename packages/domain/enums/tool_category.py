from enum import StrEnum


class ToolCategory(StrEnum):
    SEARCH = "SEARCH"
    DATABASE = "DATABASE"
    API = "API"
    FILE = "FILE"
    EMAIL = "EMAIL"
    NOTIFICATION = "NOTIFICATION"
    AI = "AI"
    UTILITY = "UTILITY"
    CUSTOM = "CUSTOM"