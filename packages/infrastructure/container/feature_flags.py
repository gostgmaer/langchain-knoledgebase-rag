# Container feature flags setup
from __future__ import annotations

from dependency_injector import containers, providers

from packages.application.services.feature_flag_service import FeatureFlagService


class FeatureFlagsContainer(containers.DeclarativeContainer):
    """
    Wires the dynamic Feature Flags service (docs/mvpRAG.md v1.1).
    `service` is a Singleton — its in-process TTL cache is meant to be
    shared process-wide across requests, and it takes a raw
    `session_factory` rather than a request-scoped repository (see
    FeatureFlagService's own docstring for why), so it has no
    per-request-session lifetime to worry about.
    """

    database = providers.DependenciesContainer()

    service = providers.Singleton(
        FeatureFlagService,
        session_factory=database.session_factory,
    )
