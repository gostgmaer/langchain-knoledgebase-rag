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

class SupportedModel(StrEnum):
    """Supported LLM models."""

    # ============================================================
    # Google Gemini
    # ============================================================

    # Gemini Chat
    GEMINI_2_5_PRO = "gemini-2.5-pro"
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    GEMINI_3_1_FLASH_LITE = "gemini-3.1-flash-lite"

    # Gemini Embeddings
    GEMINI_EMBEDDING_2 = "gemini-embedding-2"
    GEMINI_EMBEDDING_001 = "gemini-embedding-001"
    # Gemma
    GEMMA_3_1B = "gemma-3-1b-it"
    GEMMA_3_4B = "gemma-3-4b-it"
    GEMMA_3_12B = "gemma-3-12b-it"
    GEMMA_3_27B = "gemma-3-27b-it"
    GEMMA_4_31B = "gemma-4-31b-it"

    GEMMA_3N_E2B = "gemma-3n-e2b-it"
    GEMMA_3N_E4B = "gemma-3n-e4b-it"

    # ============================================================
    # OpenAI
    # ============================================================

    GPT_5 = "gpt-5"
    GPT_5_MINI = "gpt-5-mini"
    GPT_4O = "gpt-4o"

    # ============================================================
    # Anthropic
    # ============================================================

    CLAUDE_OPUS_4 = "claude-opus-4"
    CLAUDE_SONNET_4 = "claude-sonnet-4"
    CLAUDE_HAIKU_3_5 = "claude-3-5-haiku-latest"

    # ============================================================
    # Mistral AI
    # ============================================================

    MISTRAL_LARGE = "mistral-large-latest"
    MISTRAL_MEDIUM = "mistral-medium-latest"
    MISTRAL_SMALL = "mistral-small-latest"

    CODESTRAL = "codestral-latest"
    CODESTRAL_MAMBA = "codestral-mamba-latest"

    DEVSTRAL_SMALL = "devstral-small-latest"

    PIXTRAL_LARGE = "pixtral-large-latest"
    PIXTRAL_12B = "pixtral-12b"

    OPEN_MISTRAL_NEMO = "open-mistral-nemo"

    MINISTRAL_8B = "ministral-8b-latest"
    MINISTRAL_3B = "ministral-3b-latest"

    # ============================================================
    # Groq Hosted Models
    # ============================================================

    GROQ_LLAMA_3_1_8B = "llama-3.1-8b-instant"
    GROQ_LLAMA_4_SCOUT = "meta-llama/llama-4-scout-17b-16e-instruct"
    GROQ_LLAMA_4_MAVERICK = "meta-llama/llama-4-maverick-17b-128e-instruct"

    GROQ_QWEN3_32B = "qwen/qwen3-32b"
    GROQ_QWEN3_27B = "qwen/qwen3.6-27b"

    GROQ_KIMI_K2 = "moonshotai/kimi-k2-instruct-0905"

    GROQ_GPT_OSS_120B = "openai/gpt-oss-120b"
    GROQ_GPT_OSS_20B = "openai/gpt-oss-20b"

    GROQ_DEEPSEEK_R1 = "deepseek-r1-distill-llama-70b"
    GROQ_DEEPSEEK_R1_QWEN = "deepseek-r1-distill-qwen-32b"

    GROQ_GEMMA2_9B = "gemma2-9b-it"

    GROQ_MISTRAL_SABA = "mistral-saba-24b"

    GROQ_LLAMA_GUARD = "meta-llama/llama-guard-4-12b"
    GROQ_PROMPT_GUARD = "meta-llama/llama-prompt-guard-2-86m"
