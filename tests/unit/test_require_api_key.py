"""
packages/infrastructure/ai/exceptions.py's require_api_key() — the
shared pre-flight check each of the 4 real provider classes
(packages/infrastructure/ai/providers/{google,openai,anthropic,groq}.py)
now calls before ever instantiating a LangChain client. Live-verified
separately against the real app: the configured Google key still
works unchanged, and switching LLM_PROVIDER to a genuinely
unconfigured one (anthropic, whose key is blank in this dev .env)
raises this exact error instead of a raw provider-SDK exception deep
in a chat turn.
"""

import pytest

from packages.infrastructure.ai.exceptions import (
    ProviderNotConfiguredError,
    require_api_key,
)


def test_a_real_key_is_returned_unchanged():
    assert require_api_key("sk-real-key", env_var="X_API_KEY", provider="x") == "sk-real-key"


def test_none_raises_with_the_provider_and_env_var_named():
    with pytest.raises(ProviderNotConfiguredError, match="X_API_KEY"):
        require_api_key(None, env_var="X_API_KEY", provider="x")


def test_empty_string_raises():
    with pytest.raises(ProviderNotConfiguredError):
        require_api_key("", env_var="X_API_KEY", provider="x")


def test_whitespace_only_raises():
    with pytest.raises(ProviderNotConfiguredError):
        require_api_key("   ", env_var="X_API_KEY", provider="x")


def test_error_message_names_the_actual_provider_asked_for():
    with pytest.raises(ProviderNotConfiguredError, match="anthropic"):
        require_api_key(None, env_var="ANTHROPIC_API_KEY", provider="anthropic")
