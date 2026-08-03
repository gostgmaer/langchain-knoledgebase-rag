"""
FeatureFlagService.invalidate()'s cache-key logic — the exact bug fixed
this session (see docs/BUILD_STATUS.md's Analytics + Feature Flags
entry): a global-scope write (tenant_id=None) was only ever clearing
the `(key, str(None))` cache entry, leaving the real per-tenant-keyed
entry (e.g. `(key, str(DEFAULT_TENANT_ID))`, the one TenantMiddleware
actually produces since tenant_id is never really None at read time)
stale for the rest of its TTL.

invalidate() never touches the DB, so these tests populate `._cache`
directly rather than going through get_effective() — no session_factory
needed for logic that's pure dict manipulation.
"""

from uuid import uuid4

from packages.application.services.feature_flag_service import FeatureFlagService

TENANT_A = uuid4()
TENANT_B = uuid4()


def _service_with_seeded_cache(entries: dict[tuple[str, str], bool]) -> FeatureFlagService:
    service = FeatureFlagService(session_factory=lambda: None)
    for cache_key, value in entries.items():
        service._cache[cache_key] = (value, 0.0)
    return service


def test_tenant_scoped_invalidate_only_clears_that_tenants_entry():
    service = _service_with_seeded_cache(
        {
            ("enable_rbac", str(TENANT_A)): True,
            ("enable_rbac", str(TENANT_B)): False,
        }
    )

    service.invalidate("enable_rbac", tenant_id=TENANT_A)

    assert ("enable_rbac", str(TENANT_A)) not in service._cache
    assert ("enable_rbac", str(TENANT_B)) in service._cache


def test_global_invalidate_clears_every_tenants_entry_for_that_key():
    """
    The actual regression: a global write must invalidate every cached
    entry for the key, not just the (key, "None") one — the cache has
    no record of which real tenant_ids have read this key.
    """
    service = _service_with_seeded_cache(
        {
            ("enable_rbac", str(TENANT_A)): True,
            ("enable_rbac", str(TENANT_B)): True,
            ("enable_rbac", "None"): True,
            ("other_flag", str(TENANT_A)): True,
        }
    )

    service.invalidate("enable_rbac", tenant_id=None)

    assert ("enable_rbac", str(TENANT_A)) not in service._cache
    assert ("enable_rbac", str(TENANT_B)) not in service._cache
    assert ("enable_rbac", "None") not in service._cache
    # A different key is untouched by invalidating "enable_rbac".
    assert ("other_flag", str(TENANT_A)) in service._cache


def test_invalidate_on_a_key_with_no_cached_entries_is_a_no_op():
    service = _service_with_seeded_cache({})

    service.invalidate("never_cached", tenant_id=None)  # should not raise

    assert service._cache == {}
