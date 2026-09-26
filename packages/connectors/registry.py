"""Connector registry: type name -> connector class. The rest of the platform asks it, never imports a connector."""

from __future__ import annotations

from typing import Any

from packages.connectors.base import BaseKnowledgeConnector, ConnectorInfo
from packages.connectors.models import SOURCE_TYPES

# Types the platform names but has no connector for yet: listed so the UI can show them as
# "coming soon" and the enum stays stable.
_PLANNED_DISPLAY = {
    "upload": "Uploaded documents",
    "google_drive": "Google Drive",
    "notion": "Notion",
    "github": "GitHub",
    "gitlab": "GitLab",
    "slack": "Slack",
    "dropbox": "Dropbox",
    "box": "Box",
    "jira": "Jira",
    "zendesk": "Zendesk",
    "s3": "Amazon S3",
    "azure_blob": "Azure Blob Storage",
    "email": "Email",
}


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, type[BaseKnowledgeConnector]] = {}

    def register(self, connector: type[BaseKnowledgeConnector]) -> type[BaseKnowledgeConnector]:
        if connector.type not in SOURCE_TYPES:
            raise ValueError(f"Unknown source type '{connector.type}'; add it to SOURCE_TYPES first.")
        self._connectors[connector.type] = connector
        return connector

    def is_available(self, source_type: str) -> bool:
        return source_type in self._connectors

    def get(self, source_type: str) -> type[BaseKnowledgeConnector]:
        try:
            return self._connectors[source_type]
        except KeyError as exc:
            raise KeyError(f"No connector is registered for source type '{source_type}'.") from exc

    def create(self, source_type: str, configuration: dict[str, Any], credentials: dict[str, Any] | None = None, **kwargs: Any) -> BaseKnowledgeConnector:
        return self.get(source_type)(configuration, credentials, **kwargs)

    def infos(self) -> list[ConnectorInfo]:
        """Every known type: available connectors with their schema, then the planned ones."""
        infos = [c.info() for c in sorted(self._connectors.values(), key=lambda c: c.display_name)]
        for source_type in SOURCE_TYPES:
            if source_type not in self._connectors and source_type != "upload":
                infos.append(
                    ConnectorInfo(
                        type=source_type,
                        display_name=_PLANNED_DISPLAY.get(source_type, source_type),
                        description="Planned. The connector framework supports it; the connector is not built yet.",
                        icon="database",
                        available=False,
                        credential_kind="none",
                    )
                )
        return infos


_default: ConnectorRegistry | None = None


def default_registry() -> ConnectorRegistry:
    """The process-wide registry with every built-in connector registered (lazily, once)."""
    global _default
    if _default is None:
        registry = ConnectorRegistry()
        from packages.connectors.sources import register_builtin_connectors

        register_builtin_connectors(registry)
        _default = registry
    return _default
