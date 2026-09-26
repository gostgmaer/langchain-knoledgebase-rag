"""
SharePoint and OneDrive connectors (Microsoft Graph drives).

Files are listed with the drive *delta* API: the first sync enumerates everything, later syncs ask only for
what changed (`get_changes`), including deletions, so unchanged files are neither listed, downloaded nor
embedded again. A file is identified by "<driveId>:<itemId>" (stable across rename and move) and versioned by
its eTag. Bytes are handed to the existing loaders (PDF, Word, text, markdown, HTML, CSV, JSON).
"""

from __future__ import annotations

import fnmatch
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from packages.connectors.base import ConfigField, ValidationResult
from packages.connectors.http import ConnectorHttpError
from packages.connectors.models import (
    ConnectionTestResult,
    DiscoveryContext,
    ExternalChange,
    ExternalDocument,
    ExternalDocumentContent,
    ExternalPermission,
    ExternalUser,
)
from packages.connectors.sources.microsoft_graph import GraphConnector

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".txt", ".md", ".markdown", ".html", ".htm", ".csv", ".json")


def _time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class SharePointConnector(GraphConnector):
    type = "sharepoint"
    display_name = "SharePoint"
    description = "Document libraries of a SharePoint site, kept in sync with change tracking and item permissions."
    icon = "folder-kanban"
    supports_changes = True
    notes = "Needs Graph application permissions Sites.Read.All and Files.Read.All (admin consent)."
    config_schema = (
        ConfigField("site_url", "Site URL", "url", required=True, group="connection", placeholder="https://contoso.sharepoint.com/sites/Engineering"),
        ConfigField("libraries", "Document libraries", "string_list", group="content", help="Library names. Empty = all document libraries of the site."),
        ConfigField("folders", "Only these folders", "string_list", group="content", help="Paths relative to the library root, e.g. Product Documentation. Empty = whole library."),
        ConfigField("exclude_patterns", "Skip paths matching", "string_list", group="filters", help="e.g. */Archive/*, *draft*"),
        ConfigField("extensions", "File types", "string_list", default=list(SUPPORTED_EXTENSIONS), group="filters"),
        ConfigField("max_file_size_mb", "Maximum file size (MB)", "number", default=25, minimum=1, maximum=200, group="filters"),
        ConfigField("max_files", "Maximum files", "number", default=20000, minimum=1, maximum=1000000, group="advanced"),
        *GraphConnector._graph_fields,
    )

    # ------------------------------------------------------------------ drive resolution

    async def _drives(self) -> list[dict[str, Any]]:
        parts = urlsplit(str(self.configuration["site_url"]))
        site = await self.graph_get(f"/sites/{parts.hostname}:{parts.path.rstrip('/') or '/'}")
        wanted = {n.lower() for n in self.configuration.get("libraries") or []}
        drives: list[dict[str, Any]] = []
        async for drive in self.graph_paged(f"/sites/{site['id']}/drives"):
            if drive.get("driveType") not in (None, "documentLibrary"):
                continue
            if wanted and str(drive.get("name", "")).lower() not in wanted:
                continue
            drives.append(drive)
        return drives

    async def test_connection(self) -> ConnectionTestResult:
        base = await super().test_connection()
        if not base.ok:
            return base
        try:
            drives = await self._drives()
        except ConnectorHttpError as exc:
            return ConnectionTestResult(False, f"Authenticated, but the site could not be read: {exc}", authenticated=True)
        return ConnectionTestResult(
            True, f"Connected. {len(drives)} document librar{'y' if len(drives) == 1 else 'ies'} in scope.", authenticated=True,
            details={"libraries": [d.get("name") for d in drives]},
        )

    # ------------------------------------------------------------------ item mapping

    def _wanted_item(self, item: dict[str, Any]) -> bool:
        if "file" not in item:
            return False
        name = str(item.get("name", ""))
        extensions = tuple(e.lower() for e in self.configuration.get("extensions") or SUPPORTED_EXTENSIONS)
        if not name.lower().endswith(extensions):
            return False
        if int(item.get("size") or 0) > int(float(self.configuration["max_file_size_mb"]) * 1024 * 1024):
            return False
        path = self._path(item)
        folders = [f.strip("/").lower() for f in self.configuration.get("folders") or []]
        if folders and not any(path.lower().startswith(f + "/") or path.lower() == f for f in folders):
            return False
        return not any(fnmatch.fnmatchcase(path.lower(), p.lower()) for p in self.configuration.get("exclude_patterns") or [])

    @staticmethod
    def _path(item: dict[str, Any]) -> str:
        parent = (item.get("parentReference") or {}).get("path", "") or ""
        folder = parent.split("root:", 1)[-1].strip("/")
        return f"{folder}/{item.get('name', '')}".strip("/")

    def _to_document(self, drive_id: str, drive_name: str | None, item: dict[str, Any]) -> ExternalDocument:
        created_by = ((item.get("createdBy") or {}).get("user")) or {}
        modified_by = ((item.get("lastModifiedBy") or {}).get("user")) or {}
        path = self._path(item)
        hashes = (item.get("file") or {}).get("hashes") or {}
        return ExternalDocument(
            external_id=f"{drive_id}:{item['id']}",
            title=str(item.get("name")),
            canonical_url=item.get("webUrl"),
            external_version=str(item.get("eTag") or item.get("cTag") or ""),
            updated_at=_time(item.get("lastModifiedDateTime")),
            created_at=_time(item.get("createdDateTime")),
            author=ExternalUser(id=str(created_by.get("id") or created_by.get("email") or ""), name=created_by.get("displayName"), email=created_by.get("email")) if created_by else None,
            parent_external_id=(item.get("parentReference") or {}).get("id"),
            mime_type=(item.get("file") or {}).get("mimeType"),
            metadata={
                "file_id": item["id"],
                "drive_id": drive_id,
                "library": drive_name,
                "file_name": item.get("name"),
                "mime_type": (item.get("file") or {}).get("mimeType"),
                "folder": "/".join(path.split("/")[:-1]),
                "path": path,
                "web_url": item.get("webUrl"),
                "owner": created_by.get("displayName") or created_by.get("email"),
                "modified_by": modified_by.get("displayName") or modified_by.get("email"),
                "created_at": item.get("createdDateTime"),
                "updated_at": item.get("lastModifiedDateTime"),
                "version": item.get("eTag"),
                "size": item.get("size"),
                "file_hash": hashes.get("sha1Hash") or hashes.get("quickXorHash") or hashes.get("sha256Hash"),
            },
        )

    # ------------------------------------------------------------------ discovery and changes

    async def _delta_items(self, drive_id: str, url: str | None, context: DiscoveryContext) -> AsyncIterator[dict[str, Any]]:
        """Yields delta items and stores the resulting deltaLink in context.state."""
        next_url = url or f"{self._graph}/drives/{drive_id}/root/delta"
        while next_url:
            if context.cancelled is not None and await context.cancelled():
                return
            data = await self.graph_get(next_url)
            for item in data.get("value", []):
                yield item
            if "@odata.deltaLink" in data:
                context.state.setdefault("delta", {})[drive_id] = data["@odata.deltaLink"]
            next_url = data.get("@odata.nextLink")

    async def discover(self, context: DiscoveryContext) -> AsyncIterator[ExternalDocument]:
        cap = int(self.configuration["max_files"])
        if context.limit:
            cap = min(cap, context.limit)
        yielded = 0
        for drive in await self._drives():
            drive_id, name = drive["id"], drive.get("name")
            async for item in self._delta_items(drive_id, None, context):
                if "deleted" in item or not self._wanted_item(item):
                    continue
                yielded += 1
                yield self._to_document(drive_id, name, item)
                if yielded >= cap:
                    return

    async def get_changes(self, context: DiscoveryContext) -> list[ExternalChange] | None:
        tokens: dict[str, str] = (context.state or {}).get("delta") or {}
        if not tokens:
            return None
        changes: list[ExternalChange] = []
        drives = {d["id"]: d.get("name") for d in await self._drives()}
        if set(drives) != set(tokens):
            return None  # the set of libraries changed: do a full pass
        for drive_id, link in tokens.items():
            async for item in self._delta_items(drive_id, link, context):
                external_id = f"{drive_id}:{item['id']}"
                if "deleted" in item:
                    changes.append(ExternalChange("deleted", external_id))
                elif "file" in item:
                    if self._wanted_item(item):
                        changes.append(ExternalChange("updated", external_id, self._to_document(drive_id, drives[drive_id], item)))
                    else:
                        changes.append(ExternalChange("deleted", external_id))  # moved/renamed out of scope
        return changes

    # ------------------------------------------------------------------ content and permissions

    async def fetch(self, document: ExternalDocument) -> ExternalDocumentContent:
        drive_id, _, item_id = document.external_id.partition(":")
        data = await self.graph_bytes(f"/drives/{drive_id}/items/{item_id}/content")
        return ExternalDocumentContent(data=data, file_name=str(document.metadata.get("file_name") or document.title), mime_type=document.mime_type)

    async def get_document(self, external_id: str) -> ExternalDocumentContent:
        drive_id, _, item_id = external_id.partition(":")
        item = await self.graph_get(f"/drives/{drive_id}/items/{item_id}")
        return await self.fetch(self._to_document(drive_id, None, item))

    async def get_permissions(self, document: ExternalDocument) -> list[ExternalPermission] | None:
        drive_id, _, item_id = document.external_id.partition(":")
        try:
            data = await self.graph_get(f"/drives/{drive_id}/items/{item_id}/permissions")
        except ConnectorHttpError:
            return None
        rules: list[ExternalPermission] = []
        for permission in data.get("value", []):
            roles = permission.get("roles") or []
            level = "admin" if "owner" in roles else "write" if "write" in roles else "read"
            identities = permission.get("grantedToIdentitiesV2") or ([permission["grantedToV2"]] if permission.get("grantedToV2") else [])
            for identity in identities:
                user, group = identity.get("user"), identity.get("group") or identity.get("siteGroup")
                if user:
                    rules.append(ExternalPermission("user", str(user.get("email") or user.get("id")), level, user.get("displayName")))
                elif group:
                    rules.append(ExternalPermission("group", str(group.get("id") or group.get("email") or group.get("displayName")), level, group.get("displayName")))
            link = permission.get("link") or {}
            if link.get("scope") in ("anonymous", "organization"):
                rules.append(ExternalPermission("group", "organization", "read", "Everyone in the organization"))
        return rules


class OneDriveConnector(SharePointConnector):
    type = "onedrive"
    display_name = "OneDrive"
    description = "Files from a user's OneDrive for Business, with change tracking and permissions."
    icon = "cloud"
    notes = "Needs Graph application permission Files.Read.All (admin consent) to read another user's drive."
    config_schema = (
        ConfigField("user", "User (email or id)", "string", required=True, group="connection", placeholder="alex@contoso.com"),
        *(f for f in SharePointConnector.config_schema if f.key not in ("site_url", "libraries")),
    )

    async def _drives(self) -> list[dict[str, Any]]:
        drive = await self.graph_get(f"/users/{self.configuration['user']}/drive")
        return [{**drive, "name": drive.get("name") or "OneDrive"}]
