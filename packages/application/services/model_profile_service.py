# Model profile service
from __future__ import annotations

import time
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.domain.enums.model_status import ModelStatus
from packages.infrastructure.ai.config import LLMConfig, build_llm_config_from_profile
from packages.infrastructure.repositories.model_profile import ModelProfileRepository

_CACHE_TTL_SECONDS = 30.0


class ModelProfileService:
    """
    Resolves a model_profile_id to its LLMConfig, backed by Postgres with a short in-process TTL
    cache - same shape as PlatformSettingsService/FeatureFlagService (docs/BUGS.md item 38's own
    precedent). Exists for two reasons, not just the cache itself:

    1. A real, measured per-turn Postgres round trip removed: LLMNode used to construct a fresh
       `ModelProfileRepository.get()` call on essentially every chat turn (every agent has a
       configured model_profile_id) - measured ~4-10ms (docs/BUGS.md item 69). Individually
       negligible against the 2.5-8.8s LLM round trip itself, but real, and free to remove.
    2. The actual point: this is what makes LLMNode safe to wire into a process-wide Singleton
       chain instead of a per-request Factory. The class it replaces, a bare
       `model_profile_repository: ModelProfileRepository` constructor argument, was a database
       session bound at construction time - exactly the shape that already caused a real, silent
       data-loss bug once in this app when something depending on it got wired as Singleton before
       a session existed to bind (docs/TUTORIAL_LONG_TERM_MEMORY.md's "Bug 3"). A `session_factory`
       closure has nothing to capture - every call opens, uses, and closes its own session.
    """

    def __init__(self, session_factory: Callable[[], AsyncSession] | async_sessionmaker) -> None:
        self._session_factory = session_factory
        self._cache: dict[UUID, tuple[LLMConfig | None, float]] = {}

    async def resolve_llm_config(self, model_profile_id: UUID | None) -> LLMConfig | None:
        """
        None means "use LLMChatService's own default LLMManager" - a missing id, a deleted
        profile, a DISABLED/DEPRECATED one, or a provider LLMFactory doesn't implement yet are all
        treated the same way: fail soft to the global default rather than ever failing a chat turn
        over a model-profile lookup (the exact contract LLMNode's own resolver had before this).
        """
        if model_profile_id is None:
            return None

        cached = self._cache.get(model_profile_id)
        if cached is not None and (time.monotonic() - cached[1]) < _CACHE_TTL_SECONDS:
            return cached[0]

        async with self._session_factory() as session:
            profile = await ModelProfileRepository(session).get(model_profile_id)

        if profile is None or profile.status != ModelStatus.ACTIVE:
            result = None
        else:
            result = build_llm_config_from_profile(profile)

        self._cache[model_profile_id] = (result, time.monotonic())
        return result

    def invalidate(self, model_profile_id: UUID) -> None:
        """Called after an admin edits a profile so the next chat turn doesn't serve a stale
        cached config for up to 30s."""
        self._cache.pop(model_profile_id, None)
