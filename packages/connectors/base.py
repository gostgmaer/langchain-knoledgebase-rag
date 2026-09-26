"""
The connector contract.

A connector's whole job is to turn one external system into `ExternalDocument`s and their
`ExternalDocumentContent`. It never chunks, embeds, stores or retrieves; the sync engine feeds what it
returns into the existing ingestion pipeline. Adding a connector is: subclass BaseKnowledgeConnector,
describe its settings in `config_schema`, register it (registry.py). Nothing else changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, ClassVar
from urllib.parse import urlsplit

from packages.connectors.http import ResilientHttpClient
from packages.connectors.models import (
    ConnectionTestResult,
    DiscoveryContext,
    ExternalChange,
    ExternalDocument,
    ExternalDocumentContent,
    ExternalPermission,
    ValidationResult,
)

FIELD_TYPES = ("string", "text", "url", "number", "boolean", "select", "string_list", "secret")


@dataclass(frozen=True, slots=True)
class ConfigField:
    """
    One setting of a connector. The admin UI renders its form from these, so a new connector needs no
    frontend work: `type` picks the control, `group` the wizard step it belongs to.
    """

    key: str
    label: str
    type: str = "string"
    required: bool = False
    default: Any = None
    help: str | None = None
    placeholder: str | None = None
    options: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    group: str = "content"
    """connection | content | filters | permissions | advanced"""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "type": self.type,
            "required": self.required,
            "default": self.default,
            "help": self.help,
            "placeholder": self.placeholder,
            "options": list(self.options),
            "minimum": self.minimum,
            "maximum": self.maximum,
            "group": self.group,
        }


def validate_against_schema(fields: list[ConfigField] | tuple[ConfigField, ...], values: dict[str, Any]) -> ValidationResult:
    """Generic validation from the schema: required, type, range, allowed options, URL shape."""
    errors: list[str] = []
    known = {f.key for f in fields}
    for unknown in sorted(set(values) - known):
        errors.append(f"Unknown setting '{unknown}'.")

    for f in fields:
        value = values.get(f.key)
        empty = value is None or value == "" or value == []
        if empty:
            if f.required:
                errors.append(f"'{f.label}' is required.")
            continue
        if f.type in ("string", "text", "secret") and not isinstance(value, str):
            errors.append(f"'{f.label}' must be text.")
        elif f.type == "url":
            parts = urlsplit(value) if isinstance(value, str) else None
            if not parts or parts.scheme not in ("http", "https") or not parts.netloc:
                errors.append(f"'{f.label}' must be an http(s) URL.")
        elif f.type == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"'{f.label}' must be a number.")
            else:
                if f.minimum is not None and value < f.minimum:
                    errors.append(f"'{f.label}' must be at least {f.minimum:g}.")
                if f.maximum is not None and value > f.maximum:
                    errors.append(f"'{f.label}' must be at most {f.maximum:g}.")
        elif f.type == "boolean" and not isinstance(value, bool):
            errors.append(f"'{f.label}' must be true or false.")
        elif f.type == "select" and value not in f.options:
            errors.append(f"'{f.label}' must be one of: {', '.join(f.options)}.")
        elif f.type == "string_list":
            if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
                errors.append(f"'{f.label}' must be a list of non-empty text values.")
    return ValidationResult(ok=not errors, errors=errors)


def with_defaults(fields: list[ConfigField] | tuple[ConfigField, ...], values: dict[str, Any]) -> dict[str, Any]:
    out = dict(values)
    for f in fields:
        if f.key not in out and f.default is not None:
            out[f.key] = f.default
    return out


@dataclass
class ConnectorInfo:
    """Static description of a connector type, served to the admin UI."""

    type: str
    display_name: str
    description: str
    icon: str
    available: bool
    credential_kind: str
    credential_fields: list[dict[str, Any]] = field(default_factory=list)
    config_schema: list[dict[str, Any]] = field(default_factory=list)
    supports_permissions: bool = False
    supports_changes: bool = False
    supports_webhook: bool = False
    notes: str | None = None


class BaseKnowledgeConnector(ABC):
    """See the module docstring. One instance serves one sync/test of one source."""

    type: ClassVar[str]
    display_name: ClassVar[str]
    description: ClassVar[str] = ""
    icon: ClassVar[str] = "database"
    config_schema: ClassVar[tuple[ConfigField, ...]] = ()
    credential_kind: ClassVar[str] = "none"
    """none | basic | token | oauth_client: the SHAPE of the secret this connector needs."""
    credential_fields: ClassVar[tuple[ConfigField, ...]] = ()
    supports_permissions: ClassVar[bool] = False
    supports_changes: ClassVar[bool] = False
    supports_webhook: ClassVar[bool] = False
    notes: ClassVar[str | None] = None

    def __init__(
        self,
        configuration: dict[str, Any],
        credentials: dict[str, Any] | None = None,
        *,
        http: ResilientHttpClient | None = None,
        allow_private: bool = False,
    ) -> None:
        self.configuration = with_defaults(self.config_schema, configuration or {})
        self.credentials = credentials or {}
        self.allow_private = allow_private
        self._http = http

    # ------------------------------------------------------------------ helpers

    @property
    def http(self) -> ResilientHttpClient:
        if self._http is None:
            self._http = self.build_http()
        return self._http

    def build_http(self) -> ResilientHttpClient:
        """Override to add auth headers, a different rate, etc."""
        return ResilientHttpClient(allow_private=self.allow_private)

    def auth_headers(self) -> dict[str, str]:
        """Credentials as request headers. Connectors pass these per request (see ResilientHttpClient redirects)."""
        return {}

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()

    def health_stats(self) -> dict[str, Any]:
        return self.http.stats.snapshot() if self._http is not None else {}

    @classmethod
    def info(cls, *, available: bool = True) -> ConnectorInfo:
        return ConnectorInfo(
            type=cls.type,
            display_name=cls.display_name,
            description=cls.description,
            icon=cls.icon,
            available=available,
            credential_kind=cls.credential_kind,
            credential_fields=[f.to_dict() for f in cls.credential_fields],
            config_schema=[f.to_dict() for f in cls.config_schema],
            supports_permissions=cls.supports_permissions,
            supports_changes=cls.supports_changes,
            supports_webhook=cls.supports_webhook,
            notes=cls.notes,
        )

    # ------------------------------------------------------------------ contract

    async def validate_settings(self) -> ValidationResult:
        """The settings only (schema rules). Override to add cross-field rules; call super()."""
        return validate_against_schema(self.config_schema, self.configuration)

    async def validate_credentials(self) -> ValidationResult:
        """The credential SHAPE only (never contacts the source). Override when several shapes are valid."""
        if self.credential_kind == "none":
            return ValidationResult(ok=True)
        cred = validate_against_schema(self.credential_fields, self.credentials)
        if not self.credentials:
            cred.errors.insert(0, "Credentials are required for this source.")
            cred.ok = False
        return cred

    async def validate_config(self) -> ValidationResult:
        """Settings and credential shape together."""
        settings_result = await self.validate_settings()
        creds = await self.validate_credentials()
        errors = settings_result.errors + creds.errors
        return ValidationResult(ok=not errors, errors=errors, warnings=settings_result.warnings + creds.warnings)

    @abstractmethod
    async def test_connection(self) -> ConnectionTestResult:
        """A cheap authenticated call proving the address and credentials work."""

    @abstractmethod
    def discover(self, context: DiscoveryContext) -> AsyncIterator[ExternalDocument]:
        """Yield every in-scope item (cheap metadata; content only if it had to be fetched anyway)."""

    @abstractmethod
    async def fetch(self, document: ExternalDocument) -> ExternalDocumentContent:
        """Fetch and normalise one item's content."""

    async def get_changes(self, context: DiscoveryContext) -> list[ExternalChange] | None:
        """Changes since the previous sync, or None when the source cannot say (a full discovery is used)."""
        return None

    async def get_document(self, external_id: str) -> ExternalDocumentContent:
        """Fetch one item by its external id (webhook events, single-document resync)."""
        raise NotImplementedError(f"{self.display_name} cannot fetch a single document by id.")

    async def get_permissions(self, document: ExternalDocument) -> list[ExternalPermission] | None:
        """The item's access grants, or None when the source has no permission model to read."""
        return document.permissions

    async def delete(self, document: ExternalDocument) -> None:
        """Connectors are read-only: deleting in the external system is never done by the platform."""
        raise NotImplementedError("Knowledge connectors are read-only.")
