"""
Change notifications from a source: authentication and payload parsing.

A notification either names the items that changed (then only those are refreshed) or just says "something changed"
(then a normal, incremental sync runs). Nothing in a payload is trusted beyond a list of item ids, which the connector
re-fetches from the source itself.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from typing import Any

MAX_TARGETS = 200
MAX_ID_LENGTH = 1024
_TOKEN = re.compile(r"^[A-Za-z0-9._~+/=:\-]{1,512}$")


def secret_hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def authenticated(expected_hash: str | None, header_secret: str | None, body: Any) -> bool:
    """
    The per-source secret, either in the X-Webhook-Secret header or, for Microsoft Graph (which cannot send custom
    headers), as the `clientState` of every notification in the body.
    """
    if not expected_hash:
        return False
    if header_secret and secrets.compare_digest(secret_hash(header_secret), expected_hash):
        return True
    values = body.get("value") if isinstance(body, dict) else None
    if isinstance(values, list) and values:
        states = [v.get("clientState") for v in values if isinstance(v, dict)]
        return all(isinstance(s, str) and secrets.compare_digest(secret_hash(s), expected_hash) for s in states)
    return False


def safe_validation_token(token: str | None) -> str | None:
    """Microsoft Graph's subscription handshake echoes a token back; only echo something token-shaped."""
    return token if token and _TOKEN.match(token) else None


def _clean_ids(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    ids = [str(x).strip() for x in raw if isinstance(x, (str, int)) and str(x).strip()]
    return list(dict.fromkeys(i for i in ids if len(i) <= MAX_ID_LENGTH))[:MAX_TARGETS]


def extract_external_ids(source_type: str, body: Any) -> list[str]:
    """The items a notification names, or [] when it names none (the caller then runs a normal sync)."""
    if not isinstance(body, dict):
        return []
    if "external_ids" in body:
        return _clean_ids(body["external_ids"])
    if source_type == "confluence":
        for key in ("page", "content", "blog"):
            item = body.get(key)
            if isinstance(item, dict) and item.get("id") is not None:
                return _clean_ids([item["id"]])
    return []
