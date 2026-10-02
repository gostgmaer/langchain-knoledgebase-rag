"""
Microsoft Teams connector: channel conversations as one document per thread.

A thread (root message plus replies) becomes a readable transcript, versioned by its last modification
and reply count, so an active thread is re-indexed and a quiet one never is. Only standard channels of
the teams the administrator lists are read; private channels are read only when explicitly enabled;
one-to-one and group chats are never read. Access is the channel's membership.
"""

from __future__ import annotations

import base64
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

from bs4 import BeautifulSoup

from packages.connectors.base import ConfigField
from packages.connectors.http import ConnectorHttpError
from packages.connectors.models import (
    ConnectionTestResult,
    DiscoveryContext,
    ExternalDocument,
    ExternalDocumentContent,
    ExternalPermission,
    ExternalUser,
)
from packages.connectors.sources.microsoft_graph import GraphConnector

_GUID = re.compile(r"^[0-9a-fA-F-]{36}$")
FILE_EXTENSIONS = (".pdf", ".docx", ".txt", ".md", ".markdown", ".html", ".htm", ".csv", ".json")


def _time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _message_text(message: dict[str, Any]) -> str:
    body = message.get("body") or {}
    content = body.get("content") or ""
    if body.get("contentType") == "html":
        content = BeautifulSoup(content, "lxml").get_text("\n", strip=True)
    return content.strip()


def _author(message: dict[str, Any]) -> str:
    user = ((message.get("from") or {}).get("user")) or {}
    app = ((message.get("from") or {}).get("application")) or {}
    return user.get("displayName") or app.get("displayName") or "Unknown"


class TeamsConnector(GraphConnector):
    type = "microsoft_teams"
    display_name = "Microsoft Teams"
    description = "Channel conversations of selected teams, one document per thread, with channel-membership access."
    icon = "message-square"
    notes = (
        "Reading channel messages with application permissions (ChannelMessage.Read.All) is a Microsoft "
        "'protected API': the tenant must request and be granted access. Chats are never read."
    )
    config_schema = (
        ConfigField("teams", "Teams", "string_list", required=True, group="content", help="Team ids (GUIDs) or display names."),
        ConfigField("channels", "Only these channels", "string_list", group="content", help="Channel names. Empty = every standard channel of the listed teams."),
        ConfigField("include_private_channels", "Include private channels", "boolean", default=False, group="permissions",
                    help="Only channels the credentials can already read; their membership becomes their access list."),
        ConfigField("include_replies", "Include replies", "boolean", default=True, group="content"),
        ConfigField("history_days", "History window (days)", "number", default=90, minimum=1, maximum=3650, group="filters"),
        ConfigField("include_files", "Include files shared in messages", "boolean", default=False, group="content",
                    help="Files attached to messages (PDF, Word, text, markdown, CSV ...) are indexed as their own documents with the channel's access."),
        ConfigField("max_file_size_mb", "Maximum file size (MB)", "number", default=25, minimum=1, maximum=200, group="filters"),
        ConfigField("max_threads", "Maximum threads", "number", default=5000, minimum=1, maximum=200000, group="advanced"),
        *GraphConnector._graph_fields,
    )

    async def _team_ids(self) -> list[tuple[str, str]]:
        """(id, displayName) for each configured team; names are resolved through the directory."""
        resolved: list[tuple[str, str]] = []
        for entry in self.configuration.get("teams") or []:
            if _GUID.match(entry):
                data = await self.graph_get(f"/teams/{entry}", **{"$select": "id,displayName"})
                resolved.append((data["id"], data.get("displayName") or entry))
                continue
            safe = entry.replace("'", "''")
            found = [g async for g in self.graph_paged("/groups", **{"$filter": f"displayName eq '{safe}' and resourceProvisioningOptions/Any(x:x eq 'Team')", "$select": "id,displayName"})]
            if not found:
                raise ConnectorHttpError(f"Team '{entry}' was not found.")
            resolved.append((found[0]["id"], found[0].get("displayName") or entry))
        return resolved

    async def test_connection(self) -> ConnectionTestResult:
        base = await super().test_connection()
        if not base.ok:
            return base
        try:
            teams = await self._team_ids()
        except ConnectorHttpError as exc:
            return ConnectionTestResult(False, f"Authenticated, but the teams could not be read: {exc}", authenticated=True)
        return ConnectionTestResult(True, f"Connected. {len(teams)} team(s) in scope.", authenticated=True, details={"teams": [t[1] for t in teams]})

    async def _channels(self, team_id: str) -> list[dict[str, Any]]:
        wanted = {c.lower() for c in self.configuration.get("channels") or []}
        out = []
        async for channel in self.graph_paged(f"/teams/{team_id}/channels"):
            membership = channel.get("membershipType", "standard")
            if membership == "private" and not self.configuration.get("include_private_channels"):
                continue
            if membership == "shared":
                continue
            if wanted and str(channel.get("displayName", "")).lower() not in wanted:
                continue
            out.append(channel)
        return out

    async def discover(self, context: DiscoveryContext) -> AsyncIterator[ExternalDocument]:
        cap = int(self.configuration["max_threads"])
        if context.limit:
            cap = min(cap, context.limit)
        since = datetime.now(UTC) - timedelta(days=int(self.configuration["history_days"]))
        yielded = 0
        seen_files: set[str] = set()
        for team_id, team_name in await self._team_ids():
            for channel in await self._channels(team_id):
                async for root in self.graph_paged(f"/teams/{team_id}/channels/{channel['id']}/messages", **{"$top": "50"}):
                    if context.cancelled is not None and await context.cancelled():
                        return
                    if root.get("deletedDateTime") or root.get("messageType") != "message":
                        continue
                    modified = _time(root.get("lastModifiedDateTime") or root.get("createdDateTime"))
                    if modified and modified < since:
                        continue
                    replies: list[dict[str, Any]] = []
                    if self.configuration.get("include_replies", True):
                        replies = [r async for r in self.graph_paged(f"/teams/{team_id}/channels/{channel['id']}/messages/{root['id']}/replies", **{"$top": "50"}) if not r.get("deletedDateTime") and r.get("messageType") == "message"]
                    last = max([modified] + [_time(r.get("lastModifiedDateTime") or r.get("createdDateTime")) or modified for r in replies]) if modified else None
                    thread = self._thread_document(team_id, team_name, channel, root, replies, last)
                    yielded += 1
                    yield thread
                    if self.configuration.get("include_files"):
                        async for file_doc in self._files_of(thread, [root, *replies], seen_files):
                            yield file_doc
                    if yielded >= cap:
                        return

    def _thread_document(self, team_id: str, team_name: str, channel: dict[str, Any], root: dict[str, Any], replies: list[dict[str, Any]], last: datetime | None) -> ExternalDocument:
        subject = (root.get("subject") or _message_text(root).split("\n", 1)[0])[:80] or "Conversation"
        author = ((root.get("from") or {}).get("user")) or {}
        return ExternalDocument(
            external_id=f"{team_id}:{channel['id']}:{root['id']}",
            title=f"{team_name} / {channel.get('displayName')}: {subject}",
            canonical_url=root.get("webUrl"),
            external_version=f"{last.isoformat() if last else ''}|{len(replies)}",
            updated_at=last,
            created_at=_time(root.get("createdDateTime")),
            author=ExternalUser(id=str(author.get("id") or ""), name=author.get("displayName")) if author else None,
            mime_type="text/markdown",
            metadata={
                "team_id": team_id,
                "team_name": team_name,
                "channel_id": channel["id"],
                "channel_name": channel.get("displayName"),
                "channel_type": channel.get("membershipType", "standard"),
                "message_id": root["id"],
                "thread_id": root["id"],
                "author": author.get("displayName"),
                "timestamp": root.get("createdDateTime"),
                "reply_count": len(replies),
                "source_url": root.get("webUrl"),
            },
            prefetched=ExternalDocumentContent(text=self._transcript(team_name, channel.get("displayName"), subject, root, replies), mime_type="text/markdown"),
        )

    async def _files_of(self, thread: ExternalDocument, messages: list[dict[str, Any]], seen: set[str]) -> AsyncIterator[ExternalDocument]:
        """Files referenced by a thread's messages, resolved through the Graph shares API."""
        limit = int(float(self.configuration["max_file_size_mb"]) * 1024 * 1024)
        for message in messages:
            for attachment in message.get("attachments") or []:
                url = attachment.get("contentUrl")
                if attachment.get("contentType") != "reference" or not url:
                    continue
                name = str(attachment.get("name") or "")
                if not name.lower().endswith(FILE_EXTENSIONS):
                    continue
                share = "u!" + base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
                try:
                    item = await self.graph_get(f"/shares/{share}/driveItem")
                except ConnectorHttpError:
                    continue  # no access to the file, or it is gone: the thread itself is still indexed
                drive_id = (item.get("parentReference") or {}).get("driveId")
                if not drive_id or "file" not in item or int(item.get("size") or 0) > limit:
                    continue
                external_id = f"file:{drive_id}:{item['id']}"
                if external_id in seen:
                    continue
                seen.add(external_id)
                yield self._file_document(external_id, drive_id, item, thread.metadata)

    @staticmethod
    def _file_document(external_id: str, drive_id: str, item: dict[str, Any], thread_meta: dict[str, Any]) -> ExternalDocument:
        return ExternalDocument(
            external_id=external_id,
            title=str(item.get("name")),
            canonical_url=item.get("webUrl"),
            external_version=str(item.get("eTag") or item.get("cTag") or ""),
            updated_at=_time(item.get("lastModifiedDateTime")),
            parent_external_id=f"{thread_meta.get('team_id')}:{thread_meta.get('channel_id')}:{thread_meta.get('message_id')}",
            mime_type=(item.get("file") or {}).get("mimeType"),
            metadata={
                **{k: thread_meta.get(k) for k in ("team_id", "team_name", "channel_id", "channel_name", "channel_type", "thread_id") if k in thread_meta},
                "file_id": item["id"], "drive_id": drive_id, "file_name": item.get("name"), "size": item.get("size"),
                "shared_in_thread": thread_meta.get("message_id"),
            },
        )

    @staticmethod
    def _transcript(team: str, channel: str | None, subject: str, root: dict[str, Any], replies: list[dict[str, Any]]) -> str:
        lines = [f"# {subject}", f"Microsoft Teams: {team} / {channel}", ""]
        for message in [root, *replies]:
            stamp = (message.get("createdDateTime") or "")[:16].replace("T", " ")
            prefix = "  (reply) " if message is not root else ""
            lines.append(f"{prefix}**{_author(message)}** [{stamp}]: {_message_text(message)}")
        return "\n".join(lines).strip() + "\n"

    async def fetch(self, document: ExternalDocument) -> ExternalDocumentContent:
        if document.prefetched is not None:
            return document.prefetched
        if document.external_id.startswith("file:"):
            drive_id, item_id = document.metadata["drive_id"], document.metadata["file_id"]
            data = await self.graph_bytes(f"/drives/{drive_id}/items/{item_id}/content")
            return ExternalDocumentContent(data=data, file_name=str(document.metadata.get("file_name") or document.title), mime_type=document.mime_type)
        team_id, channel_id, message_id = document.external_id.split(":", 2)
        root = await self.graph_get(f"/teams/{team_id}/channels/{channel_id}/messages/{message_id}")
        replies = [r async for r in self.graph_paged(f"/teams/{team_id}/channels/{channel_id}/messages/{message_id}/replies")]
        meta = document.metadata
        return ExternalDocumentContent(text=self._transcript(meta.get("team_name", ""), meta.get("channel_name"), document.title, root, replies), mime_type="text/markdown")

    async def get_external_document(self, external_id: str) -> ExternalDocument | None:
        try:
            if external_id.startswith("file:"):
                parts = external_id.split(":", 2)
                if len(parts) != 3:
                    return None
                _, drive_id, item_id = parts
                item = await self.graph_get(f"/drives/{drive_id}/items/{item_id}")
                if "deleted" in item or "file" not in item:
                    return None
                return self._file_document(external_id, drive_id, item, {})
            parts = external_id.split(":", 2)
            if len(parts) != 3:
                return None  # not an id this connector ever issued
            team_id, channel_id, message_id = parts
            base = f"/teams/{team_id}/channels/{channel_id}"
            root = await self.graph_get(f"{base}/messages/{message_id}")
            team = await self.graph_get(f"/teams/{team_id}", **{"$select": "id,displayName"})
            channel = await self.graph_get(base)
        except ConnectorHttpError as exc:
            if exc.status == 404:
                return None
            raise
        membership = channel.get("membershipType", "standard")
        wanted = {c.lower() for c in self.configuration.get("channels") or []}
        if root.get("deletedDateTime") or root.get("messageType") != "message" or membership == "shared":
            return None
        if membership == "private" and not self.configuration.get("include_private_channels"):
            return None
        if wanted and str(channel.get("displayName", "")).lower() not in wanted:
            return None
        replies = []
        if self.configuration.get("include_replies", True):
            replies = [r async for r in self.graph_paged(f"{base}/messages/{message_id}/replies", **{"$top": "50"}) if not r.get("deletedDateTime") and r.get("messageType") == "message"]
        stamps = [_time(m.get("lastModifiedDateTime") or m.get("createdDateTime")) for m in [root, *replies]]
        last = max((s for s in stamps if s), default=None)
        return self._thread_document(team_id, team.get("displayName") or team_id, channel, root, replies, last)

    async def get_document(self, external_id: str) -> ExternalDocumentContent:
        return await self.fetch(ExternalDocument(external_id=external_id, title=external_id))

    async def get_permissions(self, document: ExternalDocument) -> list[ExternalPermission] | None:
        team_id = document.metadata.get("team_id")
        channel_id = document.metadata.get("channel_id")
        if not team_id or not channel_id:
            return None
        path = f"/teams/{team_id}/channels/{channel_id}/members" if document.metadata.get("channel_type") == "private" else f"/teams/{team_id}/members"
        try:
            members = [m async for m in self.graph_paged(path)]
        except ConnectorHttpError:
            return None
        return [
            ExternalPermission("user", str(m.get("email") or m.get("userId")), "admin" if "owner" in (m.get("roles") or []) else "read", m.get("displayName"))
            for m in members
        ]
