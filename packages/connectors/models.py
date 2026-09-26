"""
The normalised model every connector speaks. The ingestion pipeline and retrieval only ever see these
(and the Document rows built from them), never a Confluence page, a Teams message or a Drive file.
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

# Every type the platform knows about. Only those with a registered connector are `available`;
# the rest are the extension points (adding one = a new class in connectors/sources + registration).
SOURCE_TYPES = (
    "upload",
    "web",
    "wikipedia",
    "confluence",
    "microsoft_teams",
    "sharepoint",
    "google_drive",
    "onedrive",
    "notion",
    "github",
    "gitlab",
    "slack",
    "dropbox",
    "box",
    "jira",
    "zendesk",
    "s3",
    "azure_blob",
    "email",
)

PRINCIPAL_TYPES = ("user", "group", "role")
PERMISSIONS = ("read", "write", "admin")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(slots=True)
class ExternalUser:
    id: str
    name: str | None = None
    email: str | None = None


@dataclass(slots=True)
class ExternalPermission:
    """A normalised access grant from the external system. `principal_id` is the EXTERNAL id."""

    principal_type: str
    principal_id: str
    permission: str = "read"
    display_name: str | None = None


@dataclass(slots=True)
class ExternalDocumentContent:
    """Fetched, normalised content. Exactly one of `text` (markdown/plain) or `data` (a file) is set."""

    text: str | None = None
    data: bytes | None = None
    file_name: str | None = None
    """For `data`: a name with a supported extension (.pdf, .docx, ...) so the existing loaders apply."""
    mime_type: str | None = None
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.content_hash:
            if self.text is not None:
                self.content_hash = sha256_text(self.text)
            elif self.data is not None:
                self.content_hash = sha256_bytes(self.data)


@dataclass(slots=True)
class ExternalDocument:
    """One item a source holds. Discovery yields these cheaply; `fetch` produces the content."""

    external_id: str
    title: str
    canonical_url: str | None = None
    external_version: str | None = None
    """A version/revision/etag the source assigns; equal version = unchanged (no fetch, no embed)."""
    updated_at: datetime | None = None
    created_at: datetime | None = None
    author: ExternalUser | None = None
    parent_external_id: str | None = None
    mime_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    """Source-specific facts (space key, channel name, folder path, labels ...): shown, filterable, never secrets."""
    permissions: list[ExternalPermission] | None = None
    """None = the connector cannot tell (the source's default visibility applies)."""
    prefetched: ExternalDocumentContent | None = None
    """Set when discovery had to download the content anyway (a crawler), so it is not fetched twice."""
    unchanged: bool = False
    """The connector already knows this item did not change (a conditional request returned 304)."""


@dataclass(slots=True)
class ExternalChange:
    kind: str
    """created | updated | deleted | moved | permissions"""
    external_id: str
    document: ExternalDocument | None = None


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ConnectionTestResult:
    ok: bool
    message: str
    authenticated: bool | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class KnownDocument:
    """What the platform already holds for an external id (from the previous sync)."""

    external_version: str | None
    content_hash: str | None
    metadata: dict[str, Any]


@dataclass(slots=True)
class DiscoveryContext:
    source_id: UUID
    tenant_id: UUID
    sync_id: UUID | None = None
    state: dict[str, Any] = field(default_factory=dict)
    """The source's persisted `sync_state`; a connector may read it and write new keys back."""
    limit: int | None = None
    """Preview mode: stop after this many documents."""
    lookup: Callable[[str], Awaitable[KnownDocument | None]] | None = None
    """Async lookup of what is already stored for an external id (for conditional requests)."""
    cancelled: Callable[[], Awaitable[bool]] | None = None


SyncContext = DiscoveryContext
