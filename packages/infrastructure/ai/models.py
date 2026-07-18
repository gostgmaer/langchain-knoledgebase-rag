from enum import StrEnum


class LLMProvider(StrEnum):
    GOOGLE = "google"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"


class RuntimeConfig:
    DEFAULT_TEMPERATURE = 0.2
    DEFAULT_TOP_P = 0.95
    DEFAULT_TOP_K = 40