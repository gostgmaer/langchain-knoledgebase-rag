# Container platform settings setup
from __future__ import annotations

from dependency_injector import containers, providers

from packages.application.services.platform_settings_service import PlatformSettingsService


class PlatformSettingsContainer(containers.DeclarativeContainer):
    """Wires the dynamic platform settings service (docs/BUGS.md item 38) — same shape as
    FeatureFlagsContainer: a process-wide Singleton holding its own in-process TTL cache."""

    database = providers.DependenciesContainer()

    service = providers.Singleton(
        PlatformSettingsService,
        session_factory=database.session_factory,
    )
