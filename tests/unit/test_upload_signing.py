from __future__ import annotations

import hashlib
import hmac

from packages.config.loader import settings
from packages.sdk.upload._headers import SERVICE_USER_ID, identity_headers


def _expected(secret: str, user_id: str, role: str) -> str:
    # Same recipe as the Upload Service's verifyGatewaySignature().
    return hmac.new(secret.encode(), f"{user_id}::{role}".encode(), hashlib.sha256).hexdigest()


def test_no_signature_without_a_secret(monkeypatch):
    monkeypatch.setattr(settings.upload_service, "hmac_secret", None)

    headers = identity_headers("tenant-1", "user-1")

    assert headers == {"X-Tenant-Id": "tenant-1", "X-User-Id": "user-1"}


def test_signed_identity_matches_the_upload_service_recipe(monkeypatch):
    secret = "s" * 32
    monkeypatch.setattr(settings.upload_service, "hmac_secret", secret)
    monkeypatch.setattr(settings.upload_service, "service_role", "admin")

    headers = identity_headers("tenant-1", "user-1")

    assert headers["X-Tenant-Id"] == "tenant-1"
    assert headers["X-User-Id"] == "user-1"
    assert headers["X-User-Role"] == "admin"
    assert headers["X-Gateway-Hmac"] == _expected(secret, "user-1", "admin")


def test_requests_without_a_user_are_signed_as_the_service_identity(monkeypatch):
    secret = "s" * 32
    monkeypatch.setattr(settings.upload_service, "hmac_secret", secret)
    monkeypatch.setattr(settings.upload_service, "service_role", "user")

    headers = identity_headers("tenant-1")

    assert headers["X-User-Id"] == SERVICE_USER_ID
    assert headers["X-Gateway-Hmac"] == _expected(secret, SERVICE_USER_ID, "user")
