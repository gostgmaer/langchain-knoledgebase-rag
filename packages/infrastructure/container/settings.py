# Container settings
from __future__ import annotations

from dependency_injector import containers
from dependency_injector import providers

from packages.config.loader import settings


class SettingsContainer(containers.DeclarativeContainer):

    config = providers.Object(settings)
    