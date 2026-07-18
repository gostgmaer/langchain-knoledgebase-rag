from enum import StrEnum


class ModelProvider(StrEnum):
    OPENAI = "OPENAI"
    ANTHROPIC = "ANTHROPIC"
    GOOGLE = "GOOGLE"
    GROQ = "GROQ"
    MISTRAL = "MISTRAL"
    OLLAMA = "OLLAMA"
    OPENROUTER = "OPENROUTER"
    FIREWORKS = "FIREWORKS"
    TOGETHER = "TOGETHER"
    COHERE = "COHERE"
    CUSTOM = "CUSTOM"