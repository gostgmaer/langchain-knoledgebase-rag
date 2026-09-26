"""Concrete connectors. Adding one = a class in this package plus a line in register_builtin_connectors."""

from __future__ import annotations

from packages.connectors.registry import ConnectorRegistry


def register_builtin_connectors(registry: ConnectorRegistry) -> None:
    from packages.connectors.sources.confluence import ConfluenceConnector
    from packages.connectors.sources.sharepoint import OneDriveConnector, SharePointConnector
    from packages.connectors.sources.teams import TeamsConnector
    from packages.connectors.sources.web import WebConnector
    from packages.connectors.sources.wikipedia import WikipediaConnector

    for connector in (
        WebConnector,
        WikipediaConnector,
        ConfluenceConnector,
        TeamsConnector,
        SharePointConnector,
        OneDriveConnector,
    ):
        registry.register(connector)
