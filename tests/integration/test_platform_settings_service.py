"""
PlatformSettingsService (packages/application/services/platform_settings_service.py) — zero direct
test coverage before this (docs/BUGS.md F3) despite being the only path to the 13 operational knobs
in SETTINGS (rate limits, CORS origins, retention windows, retrieval strategy, ...) an admin can
change without a redeploy. Real Postgres via the `session_factory` fixture (tests/conftest.py).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from packages.application.services.platform_settings_service import (
    SETTINGS,
    PlatformSettingsService,
    default_value,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_get_falls_back_to_the_built_in_default_when_no_row_exists(session_factory):
    service = PlatformSettingsService(session_factory)

    assert await service.get("rate_limit_requests_per_minute") == default_value(
        "rate_limit_requests_per_minute"
    )


@pytest.mark.asyncio
async def test_set_then_get_returns_the_override_not_the_default(session_factory):
    service = PlatformSettingsService(session_factory)

    await service.set("rate_limit_requests_per_minute", 500, updated_by=uuid4())

    assert await service.get("rate_limit_requests_per_minute") == 500


@pytest.mark.asyncio
async def test_set_none_reverts_an_overridden_key_back_to_its_default(session_factory):
    service = PlatformSettingsService(session_factory)
    await service.set("session_expiry_days", 7, updated_by=uuid4())
    assert await service.get("session_expiry_days") == 7

    await service.set("session_expiry_days", None, updated_by=uuid4())

    assert await service.get("session_expiry_days") == default_value("session_expiry_days")


@pytest.mark.asyncio
async def test_set_none_on_a_key_with_no_override_row_is_a_harmless_no_op(session_factory):
    service = PlatformSettingsService(session_factory)

    await service.set("reindex_stale_after_days", None, updated_by=uuid4())  # must not raise

    assert await service.get("reindex_stale_after_days") == default_value("reindex_stale_after_days")


@pytest.mark.asyncio
async def test_cors_origins_list_default_is_returned_as_a_copy_not_the_registrys_own_list(session_factory):
    service = PlatformSettingsService(session_factory)

    value = await service.get("cors_origins")
    value.append("https://evil.example.com")

    fresh = PlatformSettingsService(session_factory)
    second_read = await fresh.get("cors_origins")
    assert "https://evil.example.com" not in second_read


@pytest.mark.asyncio
async def test_cached_read_does_not_see_a_set_made_through_a_different_service_instance(session_factory):
    reader = PlatformSettingsService(session_factory)
    writer = PlatformSettingsService(session_factory)
    assert await reader.get("rag_context_token_budget") == default_value("rag_context_token_budget")

    await writer.set("rag_context_token_budget", 8000, updated_by=uuid4())

    assert await reader.get("rag_context_token_budget") == default_value("rag_context_token_budget")
    reader.invalidate("rag_context_token_budget")
    assert await reader.get("rag_context_token_budget") == 8000


@pytest.mark.asyncio
async def test_seed_defaults_is_idempotent_and_never_overwrites_an_existing_override(session_factory):
    service = PlatformSettingsService(session_factory)
    await service.set("connector_sync_concurrency", 16, updated_by=uuid4())
    service.invalidate("connector_sync_concurrency")

    await service.seed_defaults()
    await service.seed_defaults()  # second call must not raise or touch the override

    service.invalidate("connector_sync_concurrency")
    assert await service.get("connector_sync_concurrency") == 16


@pytest.mark.asyncio
async def test_effective_values_covers_every_known_setting(session_factory):
    service = PlatformSettingsService(session_factory)

    values = await service.effective_values()

    assert set(values) == {spec.key for spec in SETTINGS}


@pytest.mark.parametrize(
    ("key", "value", "expected_error_substring"),
    [
        ("rate_limit_requests_per_minute", -1, "at least"),
        ("rate_limit_requests_per_minute", "not-a-number", "whole number"),
        ("retrieval_keyword_weight", 5.0, "at most"),
        ("retrieval_strategy", "mmr", "must be one of"),
        ("cors_origins", "http://example.com", "list of non-empty"),
    ],
)
def test_validate_rejects_out_of_range_or_wrong_typed_values(key, value, expected_error_substring):
    spec = next(s for s in SETTINGS if s.key == key)

    error = spec.validate(value)

    assert error is not None
    assert expected_error_substring in error


def test_validate_accepts_every_settings_own_built_in_default():
    for spec in SETTINGS:
        assert spec.validate(spec.default) is None
