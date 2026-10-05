"""
Generation/hashing for this app's own API keys (docs/BUGS.md item 33) — a tenant-scoped
credential for programmatic access, independent of an IAM-issued browser session.

`KEY_PREFIX` doubles as the detection signal `AuthService.resolve()` (packages/auth/service.py)
uses to tell an API key apart from a real IAM JWT, without needing to parse/decode anything first
— cheap and unambiguous, since a real token never starts with it.
"""

from __future__ import annotations

import hashlib
import secrets

KEY_PREFIX = "rag_live_"

# Enough of the raw value to let an admin recognize which key is which in a list
# (prefix + a few random chars) without ever re-exposing the secret itself.
_DISPLAY_LENGTH = len(KEY_PREFIX) + 8


def generate_api_key() -> tuple[str, str, str]:
    """Returns (raw_key, display_prefix, key_hash). The raw key is never stored — only key_hash."""
    raw = KEY_PREFIX + secrets.token_urlsafe(32)
    return raw, raw[:_DISPLAY_LENGTH], hash_api_key(raw)


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def looks_like_api_key(token: str) -> bool:
    return token.startswith(KEY_PREFIX)
