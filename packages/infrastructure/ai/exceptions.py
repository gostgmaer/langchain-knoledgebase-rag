class AIError(Exception):
    """Base AI exception."""


class ProviderNotSupportedError(AIError):
    """Raised when provider is unsupported."""


class ModelInitializationError(AIError):
    """Raised when model initialization fails."""

class InvalidProviderError(AIError):
    """Raised when an invalid provider is specified."""


class ProviderNotConfiguredError(AIError):
    """
    Raised when a supported provider has no API key configured.
    Distinguishes "you asked for a real provider but it has no
    credentials" (a clear, fixable configuration problem, caught
    before ever calling out to the provider) from
    `ProviderNotSupportedError` ("this provider name doesn't exist at
    all"). Without this, a missing key surfaced only on the first
    real LLM call, deep inside a chat turn, as an unhandled provider
    SDK exception.
    """


def require_api_key(api_key: str | None, *, env_var: str, provider: str) -> str:
    """
    Shared pre-flight check called by each concrete provider
    (packages/infrastructure/ai/providers/{google,openai,anthropic,groq}.py)
    at the top of `_create_model()`, before ever instantiating the
    real LangChain client — a missing/blank key used to only surface
    on the first real LLM call, as a raw provider-SDK exception with
    no indication of which `.env` variable was the actual problem.
    """
    if not api_key or not api_key.strip():
        raise ProviderNotConfiguredError(
            f"LLM_PROVIDER is set to '{provider}' but {env_var} is "
            f"missing or blank in .env — set a real API key before "
            f"starting the app."
        )
    return api_key