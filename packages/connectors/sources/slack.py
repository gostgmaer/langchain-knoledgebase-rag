"""
Slack connector: channel conversations as one document per thread (or standalone message), with
channel-membership access for private channels.

Slack's Web API answers almost everything with HTTP 200 and an `{"ok": false, "error": "..."}`
body on failure, so unlike every other connector here, auth failures are read from the body, not
the status code (see `_call`). The bot can only read a channel it has actually been invited to —
`conversations.list` is filtered to `is_member` channels for that reason, matching how Teams'
`include_private_channels` only ever sees channels the credentials can already read.
"""

from __future__ import annotations

import html
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

from packages.connectors.base import BaseKnowledgeConnector, ConfigField
from packages.connectors.http import AuthenticationFailed, ConnectorHttpError, ResilientHttpClient
from packages.connectors.models import (
    ConnectionTestResult,
    DiscoveryContext,
    ExternalDocument,
    ExternalDocumentContent,
    ExternalPermission,
    ExternalUser,
)

API = "https://slack.com/api"
FILE_EXTENSIONS = (".pdf", ".docx", ".txt", ".md", ".markdown", ".html", ".htm", ".csv", ".json")

_MENTION = re.compile(r"<@([UW][A-Z0-9]+)(?:\|([^>]+))?>")
_CHANNEL_REF = re.compile(r"<#([CG][A-Z0-9]+)(?:\|([^>]+))?>")
_LINK = re.compile(r"<(https?://[^|>]+)(?:\|([^>]+))?>")

# Auth/permission-shaped Slack error codes -> AuthenticationFailed, so a sync can mark the source
# "disconnected" rather than "error" — the same distinction every other connector here makes.
_AUTH_ERRORS = {"invalid_auth", "not_authed", "account_inactive", "token_revoked", "token_expired", "missing_scope"}

UserCache = dict[str, dict[str, "str | None"]]


def _ts_to_dt(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=UTC)
    except (TypeError, ValueError):
        return None


def _render(text: str, users: UserCache) -> str:
    """Slack 'mrkdwn' -> plain markdown: mentions and channel refs resolved to real names, link
    syntax converted, HTML entities Slack escapes in message bodies (&amp; etc.) unescaped."""
    text = _MENTION.sub(lambda m: "@" + (users.get(m.group(1), {}).get("name") or m.group(2) or m.group(1)), text)
    text = _CHANNEL_REF.sub(lambda m: "#" + (m.group(2) or m.group(1)), text)
    text = _LINK.sub(lambda m: f"[{m.group(2)}]({m.group(1)})" if m.group(2) else m.group(1), text)
    return html.unescape(text)


def _external_user(user_id: str | None, users: UserCache) -> ExternalUser | None:
    if not user_id:
        return None
    info = users.get(user_id, {})
    return ExternalUser(id=user_id, name=info.get("name"), email=info.get("email"))


def _transcript(channel: str | None, root: dict[str, Any], replies: list[dict[str, Any]], users: UserCache) -> str:
    lines = [f"# #{channel}", ""]
    for message in [root, *replies]:
        stamp = (_ts_to_dt(message.get("ts")) or datetime.now(UTC)).strftime("%Y-%m-%d %H:%M")
        author = users.get(message.get("user") or "", {}).get("name") or message.get("username") or "Unknown"
        prefix = "  (reply) " if message is not root else ""
        lines.append(f"{prefix}**{author}** [{stamp}]: {_render(message.get('text') or '', users)}")
    return "\n".join(lines).strip() + "\n"


class SlackConnector(BaseKnowledgeConnector):
    type = "slack"
    display_name = "Slack"
    description = "Channel conversations, one document per thread, with channel-membership access for private channels."
    icon = "message-square"
    credential_kind = "token"
    supports_permissions = True
    notes = (
        "Create a Slack app (api.slack.com/apps), add the bot scopes channels:history, channels:read, "
        "groups:history, groups:read, users:read (and files:read if including files), install it to the "
        "workspace, and invite the bot to every channel it should read — a public channel the bot has not "
        "joined is invisible to it, by Slack's own permission model, not a bug here. Use the Bot User OAuth "
        "Token (xoxb-...). Webhooks are not wired for Slack; use a schedule."
    )
    config_schema = (
        ConfigField("channels", "Channels", "string_list", group="content", help="Channel names (without #) or ids. Empty = every channel the bot has joined."),
        ConfigField("exclude_channels", "Exclude channels", "string_list", group="filters"),
        ConfigField("include_private_channels", "Include private channels", "boolean", default=False, group="permissions",
                    help="Only channels the bot was invited to; their membership becomes their access list."),
        ConfigField("include_threads", "Include thread replies", "boolean", default=True, group="content"),
        ConfigField("history_days", "History window (days)", "number", default=90, minimum=1, maximum=3650, group="filters"),
        ConfigField("include_files", "Include files shared in messages", "boolean", default=False, group="content",
                    help="Files attached to messages (PDF, Word, text, markdown, CSV ...) are indexed as their own documents with the channel's access."),
        ConfigField("max_file_size_mb", "Maximum file size (MB)", "number", default=25, minimum=1, maximum=200, group="filters"),
        ConfigField("max_threads", "Maximum threads", "number", default=5000, minimum=1, maximum=200000, group="advanced"),
        ConfigField("workspace_domain", "Workspace domain", "string", group="advanced",
                    help="Your *.slack.com subdomain (e.g. 'acme' for acme.slack.com), used only to build links back to threads. Optional."),
    )
    credential_fields = (
        ConfigField("bot_token", "Bot User OAuth Token", "secret", required=True, group="connection", help="Starts with xoxb-."),
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._users: UserCache | None = None

    def build_http(self) -> ResilientHttpClient:
        # Conservative interval: conversations.history/replies sit on Slack's stricter, lower-tier
        # rate limits for apps outside the App Directory; the client's own 429/Retry-After handling
        # covers the rest.
        return ResilientHttpClient(headers={"Accept": "application/json"}, min_interval=1.0, max_concurrency=2, allow_private=self.allow_private)

    def auth_headers(self) -> dict[str, str]:
        # Attached per request, never stored on the shared client (same reasoning as Confluence's).
        return {"Authorization": f"Bearer {self.credentials.get('bot_token') or ''}"}

    async def _call(self, method: str, **params: Any) -> dict[str, Any]:
        """One Slack Web API method. Slack answers almost everything HTTP 200; failure is `ok: false`."""
        response = await self.http.get(f"{API}/{method}", params=params or None, headers=self.auth_headers(), raise_auth_errors=False)
        if response.status_code >= 400:
            raise ConnectorHttpError(f"Slack returned HTTP {response.status_code} for {method}.", status=response.status_code)
        data = response.json()
        if not data.get("ok"):
            error = data.get("error", "unknown_error")
            if error in _AUTH_ERRORS:
                raise AuthenticationFailed(f"Slack rejected the request to {method}: {error}.")
            raise ConnectorHttpError(f"Slack error from {method}: {error}.")
        return data

    async def _paged(self, method: str, items_key: str, **params: Any) -> AsyncIterator[dict[str, Any]]:
        cursor: str | None = None
        while True:
            data = await self._call(method, **params, **({"cursor": cursor} if cursor else {}))
            for item in data.get(items_key, []):
                yield item
            cursor = (data.get("response_metadata") or {}).get("next_cursor") or None
            if not cursor:
                return

    # ------------------------------------------------------------------ users (cached per sync)

    async def _user_cache(self) -> UserCache:
        if self._users is None:
            self._users = {}
            async for member in self._paged("users.list", "members", limit=200):
                profile = member.get("profile") or {}
                self._users[member["id"]] = {
                    "name": profile.get("display_name") or profile.get("real_name") or member.get("name"),
                    "email": profile.get("email"),
                }
        return self._users

    # ------------------------------------------------------------------ connection / channels

    async def test_connection(self) -> ConnectionTestResult:
        try:
            data = await self._call("auth.test")
        except AuthenticationFailed as exc:
            return ConnectionTestResult(False, str(exc), authenticated=False)
        except ConnectorHttpError as exc:
            return ConnectionTestResult(False, str(exc))
        return ConnectionTestResult(
            True, f"Connected to Slack workspace '{data.get('team')}'.", authenticated=True,
            details={"team": data.get("team"), "bot_user": data.get("user")},
        )

    async def _channels(self) -> list[dict[str, Any]]:
        wanted = {c.lower().lstrip("#") for c in self.configuration.get("channels") or []}
        excluded = {c.lower().lstrip("#") for c in self.configuration.get("exclude_channels") or []}
        include_private = bool(self.configuration.get("include_private_channels"))
        types = "public_channel" + (",private_channel" if include_private else "")
        out = []
        async for channel in self._paged("conversations.list", "channels", types=types, limit=200, exclude_archived="true"):
            if not channel.get("is_member"):
                continue  # the bot cannot read a channel it has not joined, whatever scopes it has
            if channel.get("is_private") and not include_private:
                continue  # defence in depth: never rely solely on the `types` request param
            name = str(channel.get("name", "")).lower()
            # `wanted`/`excluded` are lower-cased, but Slack channel ids are upper-case (e.g. "C0123456789"):
            # comparing the raw id against them never matched, silently breaking id-based allow/exclude lists.
            channel_id = str(channel.get("id", "")).lower()
            if wanted and name not in wanted and channel_id not in wanted:
                continue
            if name in excluded or channel_id in excluded:
                continue
            out.append(channel)
        return out

    # ------------------------------------------------------------------ discovery

    async def discover(self, context: DiscoveryContext) -> AsyncIterator[ExternalDocument]:
        cap = int(self.configuration["max_threads"])
        if context.limit:
            cap = min(cap, context.limit)
        oldest = str((datetime.now(UTC) - timedelta(days=int(self.configuration["history_days"]))).timestamp())
        users = await self._user_cache()
        yielded = 0
        seen_files: set[str] = set()
        for channel in await self._channels():
            async for message in self._paged("conversations.history", "messages", channel=channel["id"], oldest=oldest, limit=200):
                if context.cancelled is not None and await context.cancelled():
                    return
                if message.get("subtype") in ("channel_join", "channel_leave", "channel_topic", "channel_purpose"):
                    continue
                if message.get("thread_ts") and message["thread_ts"] != message.get("ts"):
                    continue  # a reply: picked up under its root thread below
                replies: list[dict[str, Any]] = []
                if self.configuration.get("include_threads", True) and message.get("reply_count"):
                    replies = [
                        r async for r in self._paged("conversations.replies", "messages", channel=channel["id"], ts=message["ts"], limit=200)
                        if r.get("ts") != message.get("ts")
                    ]
                thread = self._thread_document(channel, message, replies, users)
                yielded += 1
                yield thread
                if self.configuration.get("include_files"):
                    async for file_doc in self._files_of(channel, [message, *replies], seen_files):
                        yield file_doc
                if yielded >= cap:
                    return

    def _thread_document(self, channel: dict[str, Any], root: dict[str, Any], replies: list[dict[str, Any]], users: UserCache) -> ExternalDocument:
        subject = _render(root.get("text") or "", users).split("\n", 1)[0][:80] or "Message"
        last_ts = max([root.get("ts")] + [r.get("ts") for r in replies], key=lambda t: float(t or 0))
        domain = self.configuration.get("workspace_domain")
        url = f"https://{domain}.slack.com/archives/{channel['id']}/p{str(root['ts']).replace('.', '')}" if domain else None
        return ExternalDocument(
            external_id=f"{channel['id']}:{root['ts']}",
            title=f"#{channel.get('name')}: {subject}",
            canonical_url=url,
            external_version=f"{last_ts}|{len(replies)}",
            updated_at=_ts_to_dt(last_ts),
            created_at=_ts_to_dt(root.get("ts")),
            author=_external_user(root.get("user"), users),
            mime_type="text/markdown",
            metadata={
                "channel_id": channel["id"],
                "channel_name": channel.get("name"),
                "channel_type": "private" if channel.get("is_private") else "public",
                "thread_ts": root["ts"],
                "author": users.get(root.get("user") or "", {}).get("name"),
                "reply_count": len(replies),
                "source_url": url,
            },
            prefetched=ExternalDocumentContent(text=_transcript(channel.get("name"), root, replies, users), mime_type="text/markdown"),
        )

    async def _files_of(self, channel: dict[str, Any], messages: list[dict[str, Any]], seen: set[str]) -> AsyncIterator[ExternalDocument]:
        """Files attached to a thread's messages. Slack includes file metadata inline on the message, no extra call."""
        limit = int(float(self.configuration["max_file_size_mb"]) * 1024 * 1024)
        for message in messages:
            for f in message.get("files") or []:
                name = str(f.get("name") or "")
                if not name.lower().endswith(FILE_EXTENSIONS) or f.get("id") in seen:
                    continue
                if int(f.get("size") or 0) > limit or not f.get("url_private_download"):
                    continue
                seen.add(f["id"])
                yield ExternalDocument(
                    external_id=f"file:{channel['id']}:{f['id']}",
                    title=name,
                    canonical_url=f.get("permalink"),
                    external_version=str(f.get("timestamp") or ""),
                    updated_at=_ts_to_dt(str(f["timestamp"])) if f.get("timestamp") else None,
                    parent_external_id=f"{channel['id']}:{message.get('thread_ts') or message.get('ts')}",
                    mime_type=f.get("mimetype"),
                    metadata={
                        "channel_id": channel["id"], "channel_name": channel.get("name"),
                        "file_id": f["id"], "file_name": name, "download_url": f["url_private_download"], "size": f.get("size"),
                    },
                )

    # ------------------------------------------------------------------ content and permissions

    async def fetch(self, document: ExternalDocument) -> ExternalDocumentContent:
        if document.prefetched is not None:
            return document.prefetched
        if document.external_id.startswith("file:"):
            response = await self.http.get(document.metadata["download_url"], headers=self.auth_headers())
            if response.status_code >= 400:
                raise ConnectorHttpError(f"File download failed (HTTP {response.status_code}).", status=response.status_code)
            return ExternalDocumentContent(data=response.content, file_name=str(document.metadata.get("file_name") or document.title), mime_type=document.mime_type)
        channel_id, thread_ts = document.external_id.split(":", 1)
        root, replies = await self._thread_messages(channel_id, thread_ts)
        users = await self._user_cache()
        return ExternalDocumentContent(text=_transcript(document.metadata.get("channel_name"), root, replies, users), mime_type="text/markdown")

    async def _thread_messages(self, channel_id: str, thread_ts: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        root_resp = await self._call("conversations.history", channel=channel_id, latest=thread_ts, oldest=thread_ts, inclusive="true", limit=1)
        root = (root_resp.get("messages") or [{}])[0]
        replies = [
            r async for r in self._paged("conversations.replies", "messages", channel=channel_id, ts=thread_ts, limit=200)
            if r.get("ts") != thread_ts
        ] if self.configuration.get("include_threads", True) and root.get("reply_count") else []
        return root, replies

    async def get_external_document(self, external_id: str) -> ExternalDocument | None:
        if external_id.startswith("file:"):
            raise NotImplementedError("Files are refreshed with their thread.")
        try:
            channel_id, thread_ts = external_id.split(":", 1)
        except ValueError:
            return None
        try:
            root, replies = await self._thread_messages(channel_id, thread_ts)
            if not root:
                return None
            channel = (await self._call("conversations.info", channel=channel_id))["channel"]
        except ConnectorHttpError:
            return None
        users = await self._user_cache()
        return self._thread_document(channel, root, replies, users)

    async def get_document(self, external_id: str) -> ExternalDocumentContent:
        return await self.fetch(ExternalDocument(external_id=external_id, title=external_id))

    async def get_permissions(self, document: ExternalDocument) -> list[ExternalPermission] | None:
        if document.metadata.get("channel_type") != "private":
            return None  # public channel: the source's default visibility applies
        channel_id = document.metadata.get("channel_id")
        if not channel_id:
            return None
        try:
            member_ids = [m async for m in self._paged("conversations.members", "members", channel=channel_id, limit=200)]
        except ConnectorHttpError:
            return None
        users = await self._user_cache()
        return [ExternalPermission("user", uid, "read", users.get(uid, {}).get("name")) for uid in member_ids]
