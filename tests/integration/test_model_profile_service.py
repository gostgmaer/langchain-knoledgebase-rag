"""
ModelProfileService (packages/application/services/model_profile_service.py) — new (docs/BUGS.md
item 69). Resolves a model_profile_id to its LLMConfig with a short TTL cache, replacing LLMNode's
old per-call ModelProfileRepository.get() — real Postgres via the `session_factory` fixture
(tests/conftest.py), same pattern as test_platform_settings_service.py.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from packages.application.services.model_profile_service import ModelProfileService
from packages.domain.enums.model_provider import ModelProvider
from packages.domain.enums.model_status import ModelStatus
from packages.domain.models.model_profile import ModelProfile
from packages.infrastructure.ai.models import LLMProvider

pytestmark = pytest.mark.integration


def _profile(*, status=ModelStatus.ACTIVE, provider=ModelProvider.GOOGLE) -> ModelProfile:
    # (provider, model) is uniquely constrained - a distinct model string per test profile avoids
    # collisions between tests/parallel runs.
    return ModelProfile(
        name=f"test-profile-{uuid4()}",
        provider=provider,
        model=f"gemini-3.1-flash-lite-{uuid4()}",
        temperature=0.7,
        top_p=1.0,
        max_tokens=1024,
        context_window=32000,
        embedding_dimensions=1536,
        vector=[0.0] * 1536,
        status=status,
    )


@pytest.mark.asyncio
async def test_resolves_an_active_profile_to_a_real_llm_config(db_session, session_factory):
    profile = _profile()
    db_session.add(profile)
    await db_session.commit()
    service = ModelProfileService(session_factory)

    config = await service.resolve_llm_config(profile.id)

    assert config is not None
    assert config.provider == LLMProvider.GOOGLE
    assert config.model == profile.model
    assert config.temperature == 0.7


@pytest.mark.asyncio
async def test_none_id_resolves_to_none_without_touching_the_database():
    service = ModelProfileService(lambda: (_ for _ in ()).throw(AssertionError("should not be called")))

    assert await service.resolve_llm_config(None) is None


@pytest.mark.asyncio
async def test_a_missing_profile_resolves_to_none(session_factory):
    service = ModelProfileService(session_factory)

    assert await service.resolve_llm_config(uuid4()) is None


@pytest.mark.asyncio
async def test_a_disabled_profile_resolves_to_none(db_session, session_factory):
    profile = _profile(status=ModelStatus.DISABLED)
    db_session.add(profile)
    await db_session.commit()
    service = ModelProfileService(session_factory)

    assert await service.resolve_llm_config(profile.id) is None


@pytest.mark.asyncio
async def test_a_cached_read_does_not_see_a_status_change_until_invalidated(db_session, session_factory):
    profile = _profile()
    db_session.add(profile)
    await db_session.commit()
    service = ModelProfileService(session_factory)
    assert await service.resolve_llm_config(profile.id) is not None

    profile.status = ModelStatus.DISABLED
    await db_session.commit()

    assert await service.resolve_llm_config(profile.id) is not None  # still cached
    service.invalidate(profile.id)
    assert await service.resolve_llm_config(profile.id) is None  # fresh read now sees it


@pytest.mark.asyncio
async def test_two_different_profile_ids_cache_independently(db_session, session_factory):
    active = _profile()
    disabled = _profile(status=ModelStatus.DISABLED)
    db_session.add_all([active, disabled])
    await db_session.commit()
    service = ModelProfileService(session_factory)

    assert await service.resolve_llm_config(active.id) is not None
    assert await service.resolve_llm_config(disabled.id) is None
