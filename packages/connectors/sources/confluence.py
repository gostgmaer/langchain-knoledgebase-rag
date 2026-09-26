"""
Confluence connector (Cloud, Server and Data Center) on the official REST API.

Discovery lists pages with CQL (metadata only), so a sync of an unchanged space downloads no page bodies:
a page is fetched only when its version number changed. Bodies come from `body.view` (rendered HTML,
macros expanded) and go through the same HTML -> markdown extraction as the web connector. Page-level
read restrictions are read as permissions; a page with none is visible to whoever sees the space, which the
API cannot enumerate without space-admin rights, so the source's default visibility applies.
"""

from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any
from urllib.parse import quote, urljoin

from packages.connectors.base import BaseKnowledgeConnector, ConfigField, ValidationResult
from packages.connectors.html_extract import html_to_markdown
from packages.connectors.http import AuthenticationFailed, ConnectorHttpError, ResilientHttpClient
from packages.connectors.models import (
    ConnectionTestResult,
    DiscoveryContext,
    ExternalDocument,
    ExternalDocumentContent,
    ExternalPermission,
    ExternalUser,
)

PAGE_SIZE = 50
ATTACHMENT_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/csv": ".csv",
}


def _time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _cql_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


class ConfluenceConnector(BaseKnowledgeConnector):
    type = "confluence"
    display_name = "Confluence"
    description = "Pages (and optionally attachments) from selected Confluence spaces, with page restrictions."
    icon = "book"
    credential_kind = "token"
    supports_permissions = True
    notes = (
        "Cloud: use your Atlassian email and an API token. Server/Data Center: leave the email empty and use a "
        "personal access token. Webhooks are not wired for Confluence; use a schedule."
    )
    config_schema = (
        ConfigField("base_url", "Confluence URL", "url", required=True, group="connection",
                    help="Cloud: https://your-team.atlassian.net/wiki. Server: https://confluence.example.com",
                    placeholder="https://your-team.atlassian.net/wiki"),
        ConfigField("spaces", "Include spaces (keys)", "string_list", group="content", help="Space keys such as ENG, HR. Empty = every space the account can read."),
        ConfigField("exclude_spaces", "Exclude spaces (keys)", "string_list", group="filters"),
        ConfigField("include_personal_spaces", "Include personal spaces", "boolean", default=False, group="filters"),
        ConfigField("include_archived", "Include archived content", "boolean", default=False, group="filters"),
        ConfigField("parent_page_ids", "Only under these pages (ids)", "string_list", group="content", help="Include a page and everything beneath it."),
        ConfigField("labels", "Only pages with a label", "string_list", group="filters"),
        ConfigField("exclude_labels", "Skip pages with a label", "string_list", group="filters"),
        ConfigField("content_types", "Content types", "string_list", default=["page"], group="content", help="page and/or blogpost."),
        ConfigField("include_attachments", "Include attachments", "boolean", default=False, group="content",
                    help="PDF, Word, text, markdown and CSV attachments are indexed as their own documents."),
        ConfigField("max_pages", "Maximum documents", "number", default=5000, minimum=1, maximum=200000, group="advanced"),
    )
    credential_fields = (
        ConfigField("email", "Account email", "string", group="connection", help="Cloud only. Leave empty for a personal access token."),
        ConfigField("api_token", "API token / personal access token", "secret", required=True, group="connection"),
    )

    def build_http(self) -> ResilientHttpClient:
        return ResilientHttpClient(
            headers={"Accept": "application/json"},
            min_interval=0.2,
            max_concurrency=3,
            allow_private=self.allow_private,
        )

    def auth_headers(self) -> dict[str, str]:
        # Attached per request, never stored on the shared client, so it cannot follow a redirect to another host.
        token = str(self.credentials.get("api_token") or "")
        email = str(self.credentials.get("email") or "")
        if email:
            return {"Authorization": "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()}
        return {"Authorization": f"Bearer {token}"}

    @property
    def _root(self) -> str:
        return str(self.configuration["base_url"]).rstrip("/")

    async def _get(self, path: str, **params: Any) -> dict[str, Any]:
        url = path if path.startswith("http") else f"{self._root}/rest/api{path}"
        response = await self.http.get(url, params=params or None, headers=self.auth_headers())
        if response.status_code >= 400:
            raise ConnectorHttpError(f"Confluence returned HTTP {response.status_code} for {path.split('?')[0]}.", status=response.status_code)
        return response.json()

    async def validate_settings(self) -> ValidationResult:
        result = await super().validate_settings()
        types = self.configuration.get("content_types") or []
        for t in types:
            if t not in ("page", "blogpost"):
                result.errors.append(f"Content type '{t}' is not supported (page, blogpost).")
        result.ok = not result.errors
        return result

    async def test_connection(self) -> ConnectionTestResult:
        try:
            data = await self._get("/space", limit=1)
        except AuthenticationFailed:
            return ConnectionTestResult(False, "Confluence rejected the credentials.", authenticated=False)
        except ConnectorHttpError as exc:
            return ConnectionTestResult(False, str(exc))
        return ConnectionTestResult(
            True, "Connected to Confluence.", authenticated=True, details={"spaces_visible": data.get("size", 0)}
        )

    # ------------------------------------------------------------------ discovery

    def _cql(self) -> str:
        c = self.configuration
        clauses = []
        types = c.get("content_types") or ["page"]
        clauses.append("type in (" + ",".join(types) + ")")
        if c.get("spaces"):
            clauses.append("space in (" + ",".join(_cql_quote(s) for s in c["spaces"]) + ")")
        if c.get("exclude_spaces"):
            clauses.append("space not in (" + ",".join(_cql_quote(s) for s in c["exclude_spaces"]) + ")")
        if c.get("parent_page_ids"):
            clauses.append("ancestor in (" + ",".join(_cql_quote(p) for p in c["parent_page_ids"]) + ")")
        if c.get("labels"):
            clauses.append("label in (" + ",".join(_cql_quote(l) for l in c["labels"]) + ")")
        if c.get("exclude_labels"):
            clauses.append("label not in (" + ",".join(_cql_quote(l) for l in c["exclude_labels"]) + ")")
        if not c.get("include_archived"):
            clauses.append("status = current")
        return " and ".join(clauses)

    def _to_document(self, item: dict[str, Any]) -> ExternalDocument | None:
        space = item.get("space") or {}
        if not self.configuration.get("include_personal_spaces") and (space.get("type") == "personal" or str(space.get("key", "")).startswith("~")):
            return None
        links = item.get("_links") or {}
        base = links.get("base") or self._root
        webui = links.get("webui") or ""
        url = urljoin(base.rstrip("/") + "/", webui.lstrip("/")) if webui else None
        version = item.get("version") or {}
        by = version.get("by") or (item.get("history") or {}).get("createdBy") or {}
        ancestors = item.get("ancestors") or []
        labels = [l.get("name") for l in ((item.get("metadata") or {}).get("labels") or {}).get("results", [])]
        return ExternalDocument(
            external_id=str(item["id"]),
            title=item.get("title") or str(item["id"]),
            canonical_url=url,
            external_version=str(version.get("number")) if version.get("number") is not None else None,
            updated_at=_time(version.get("when")),
            created_at=_time((item.get("history") or {}).get("createdDate")),
            author=ExternalUser(id=str(by.get("accountId") or by.get("userKey") or by.get("username") or ""), name=by.get("displayName") or by.get("publicName"), email=by.get("email")) if by else None,
            parent_external_id=str(ancestors[-1]["id"]) if ancestors else None,
            mime_type="text/html",
            metadata={
                "space": space.get("name"),
                "space_key": space.get("key"),
                "page_id": str(item["id"]),
                "page_title": item.get("title"),
                "parent_page_id": str(ancestors[-1]["id"]) if ancestors else None,
                "page_url": url,
                "author": by.get("displayName") or by.get("publicName"),
                "created_at": (item.get("history") or {}).get("createdDate"),
                "updated_at": version.get("when"),
                "version": version.get("number"),
                "labels": labels,
                "content_type": item.get("type"),
                "path": [a.get("title") for a in ancestors],
            },
        )

    async def discover(self, context: DiscoveryContext) -> AsyncIterator[ExternalDocument]:
        cap = int(self.configuration["max_pages"])
        if context.limit:
            cap = min(cap, context.limit)
        yielded = 0
        next_path: str | None = None
        params: dict[str, Any] | None = {
            "cql": self._cql(),
            "limit": PAGE_SIZE,
            "expand": "version,space,ancestors,metadata.labels,history",
        }
        while yielded < cap:
            if context.cancelled is not None and await context.cancelled():
                return
            data = await (self._get(next_path) if next_path else self._get("/content/search", **(params or {})))
            params = None
            for item in data.get("results", []):
                document = self._to_document(item)
                if document is None:
                    continue
                yielded += 1
                yield document
                if self.configuration.get("include_attachments"):
                    async for attachment in self._attachments(document):
                        yield attachment
                if yielded >= cap:
                    return
            link = (data.get("_links") or {}).get("next")
            if not link:
                return
            next_path = urljoin(str((data.get("_links") or {}).get("base") or self._root).rstrip("/") + "/", link.lstrip("/"))

    async def _attachments(self, page: ExternalDocument) -> AsyncIterator[ExternalDocument]:
        try:
            data = await self._get(f"/content/{page.external_id}/child/attachment", limit=100, expand="version")
        except ConnectorHttpError:
            return
        for item in data.get("results", []):
            media = ((item.get("metadata") or {}).get("mediaType")) or (item.get("extensions") or {}).get("mediaType")
            extension = ATTACHMENT_TYPES.get(media or "")
            if not extension:
                continue
            links = item.get("_links") or {}
            download = links.get("download")
            version = item.get("version") or {}
            yield ExternalDocument(
                external_id=f"att:{item['id']}",
                title=item.get("title") or item["id"],
                canonical_url=page.canonical_url,
                external_version=str(version.get("number")),
                updated_at=_time(version.get("when")),
                parent_external_id=page.external_id,
                mime_type=media,
                metadata={
                    **page.metadata,
                    "attachment_id": item["id"],
                    "attachment_of": page.title,
                    "download": urljoin(str(links.get("base") or self._root).rstrip("/") + "/", str(download or "").lstrip("/")),
                    "extension": extension,
                },
            )

    # ------------------------------------------------------------------ content and permissions

    async def fetch(self, document: ExternalDocument) -> ExternalDocumentContent:
        if document.external_id.startswith("att:"):
            response = await self.http.get(document.metadata["download"], headers=self.auth_headers())
            if response.status_code >= 400:
                raise ConnectorHttpError(f"Attachment download failed (HTTP {response.status_code}).", status=response.status_code)
            name = document.title if document.title.lower().endswith(document.metadata["extension"]) else document.title + document.metadata["extension"]
            return ExternalDocumentContent(data=response.content, file_name=name, mime_type=document.mime_type)
        data = await self._get(f"/content/{document.external_id}", expand="body.view,version")
        html = ((data.get("body") or {}).get("view") or {}).get("value") or ""
        page = html_to_markdown(f"<html><body><main>{html}</main></body></html>", document.canonical_url or self._root)
        text = page.markdown or ""
        return ExternalDocumentContent(text=f"# {document.title}\n\n{text}".strip() + "\n", mime_type="text/markdown")

    async def get_document(self, external_id: str) -> ExternalDocumentContent:
        return await self.fetch(ExternalDocument(external_id=external_id, title=external_id, canonical_url=self._root))

    async def get_permissions(self, document: ExternalDocument) -> list[ExternalPermission] | None:
        page_id = document.parent_external_id if document.external_id.startswith("att:") else document.external_id
        if document.external_id.startswith("att:"):
            page_id = document.parent_external_id
        try:
            data = await self._get(f"/content/{page_id}/restriction/byOperation/read")
        except ConnectorHttpError:
            return None
        rules: list[ExternalPermission] = []
        restrictions = data.get("restrictions") or {}
        for user in (restrictions.get("user") or {}).get("results", []):
            rules.append(ExternalPermission("user", str(user.get("accountId") or user.get("userKey") or user.get("username")), "read", user.get("displayName")))
        for group in (restrictions.get("group") or {}).get("results", []):
            rules.append(ExternalPermission("group", str(group.get("name")), "read", group.get("name")))
        return rules
