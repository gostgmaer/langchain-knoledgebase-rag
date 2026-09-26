"""
Encryption of connector credentials at rest.

Credentials are JSON encrypted with Fernet (AES-128-CBC + HMAC). The key(s) live only in the environment
(CONNECTOR_CREDENTIAL_KEYS): the first key encrypts, every key can decrypt, which is how a key is rotated
without downtime (add the new key first, run `rotate`, then drop the old one). With no key configured
nothing can be stored: the platform refuses rather than storing secrets in the clear.
"""

from __future__ import annotations

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class CredentialConfigurationError(RuntimeError):
    """CONNECTOR_CREDENTIAL_KEYS is missing or malformed."""


class CredentialDecryptionError(RuntimeError):
    """A stored credential could not be decrypted with any configured key."""


class CredentialCipher:
    def __init__(self, keys: str | None) -> None:
        raw = [k.strip() for k in (keys or "").split(",") if k.strip()]
        if not raw:
            raise CredentialConfigurationError(
                "CONNECTOR_CREDENTIAL_KEYS is not set. Generate a key with "
                "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"` "
                "and set it before connecting sources that need credentials."
            )
        try:
            self._multi = MultiFernet([Fernet(k.encode()) for k in raw])
        except (ValueError, TypeError) as exc:
            raise CredentialConfigurationError("CONNECTOR_CREDENTIAL_KEYS contains an invalid Fernet key.") from exc

    def encrypt(self, secret: dict[str, Any]) -> str:
        return self._multi.encrypt(json.dumps(secret, separators=(",", ":")).encode()).decode()

    def decrypt(self, token: str) -> dict[str, Any]:
        try:
            return json.loads(self._multi.decrypt(token.encode()))
        except InvalidToken as exc:
            raise CredentialDecryptionError("The stored credential cannot be decrypted with the configured keys.") from exc

    def rotate(self, token: str) -> str:
        """Re-encrypts with the primary (first) key."""
        try:
            return self._multi.rotate(token.encode()).decode()
        except InvalidToken as exc:
            raise CredentialDecryptionError("The stored credential cannot be decrypted with the configured keys.") from exc
