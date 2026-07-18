from enum import StrEnum


class PromptCategory(StrEnum):
    SYSTEM = "SYSTEM"
    RAG = "RAG"
    AGENT = "AGENT"
    TOOL = "TOOL"
    SUMMARIZATION = "SUMMARIZATION"
    CLASSIFICATION = "CLASSIFICATION"
    EXTRACTION = "EXTRACTION"
    CUSTOM = "CUSTOM"