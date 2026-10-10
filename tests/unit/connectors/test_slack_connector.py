from __future__ import annotations

import httpx
import pytest

from packages.connectors.http import AuthenticationFailed
from packages.connectors.sources.slack import SlackConnector
from tests.unit.connectors.helpers import client, collect, context

USERS = [
    {"id": "U1", "name": "alice", "profile": {"display_name": "Alice", "real_name": "Alice A", "email": "alice@acme.test"}},
    {"id": "U2", "name": "bob", "profile": {"display_name": "", "real_name": "Bob B", "email": "bob@acme.test"}},
]

CHANNELS = [
    {"id": "C1", "name": "general", "is_member": True, "is_private": False},
    {"id": "C2", "name": "secret", "is_member": True, "is_private": True},
    {"id": "C3", "name": "notjoined", "is_member": False, "is_private": False},
]

ROOT = {
    "ts": "1700000000.000100",
    "user": "U1",
    "text": "Hello <@U2> check <#C2|secret> and <https://example.com|docs> &amp; more",
    "reply_count": 1,
    "thread_ts": "1700000000.000100",
}
STANDALONE = {"ts": "1699999999.000000", "user": "U2", "text": "standalone message"}
REPLY = {"ts": "1700000100.000200", "user": "U2", "text": "reply text"}


def slack(config=None, handler=None, credentials=None):
    calls = []

    def default(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        params = dict(request.url.params)

        if path.endswith("/auth.test"):
            return httpx.Response(200, json={"ok": True, "team": "Acme", "user": "ragbot"})
        if path.endswith("/users.list"):
            return httpx.Response(200, json={"ok": True, "members": USERS, "response_metadata": {"next_cursor": ""}})
        if path.endswith("/conversations.list"):
            return httpx.Response(200, json={"ok": True, "channels": CHANNELS, "response_metadata": {"next_cursor": ""}})
        if path.endswith("/conversations.history"):
            if params.get("latest") == ROOT["ts"] and params.get("oldest") == ROOT["ts"]:
                return httpx.Response(200, json={"ok": True, "messages": [ROOT]})
            return httpx.Response(200, json={"ok": True, "messages": [ROOT, STANDALONE], "response_metadata": {"next_cursor": ""}})
        if path.endswith("/conversations.replies"):
            return httpx.Response(200, json={"ok": True, "messages": [ROOT, REPLY], "response_metadata": {"next_cursor": ""}})
        if path.endswith("/conversations.members"):
            return httpx.Response(200, json={"ok": True, "members": ["U1", "U2"], "response_metadata": {"next_cursor": ""}})
        if path.endswith("/conversations.info"):
            return httpx.Response(200, json={"ok": True, "channel": {"id": "C2", "name": "secret", "is_private": True}})
        return httpx.Response(404)

    connector = SlackConnector(
        config or {},
        credentials or {"bot_token": "xoxb-TOKEN"},
        http=client(handler or default, min_interval=0.0),
        allow_private=True,
    )
    connector.calls = calls  # type: ignore[attr-defined]
    return connector


@pytest.mark.asyncio
async def test_connection_succeeds_and_reports_team():
    result = await slack().test_connection()
    assert result.ok and result.authenticated is True
    assert result.details["team"] == "Acme"


@pytest.mark.asyncio
async def test_connection_failure_is_reported_not_raised():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "error": "invalid_auth"})

    result = await slack(handler=handler).test_connection()
    assert not result.ok and result.authenticated is False


@pytest.mark.asyncio
async def test_non_auth_slack_errors_raise_a_plain_connector_error():
    from packages.connectors.http import ConnectorHttpError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "error": "channel_not_found"})

    with pytest.raises(ConnectorHttpError):
        await collect(slack(handler=handler).discover(context()))


@pytest.mark.asyncio
async def test_channels_not_joined_are_never_read():
    docs = await collect(slack().discover(context()))
    assert all(d.metadata["channel_id"] != "C3" for d in docs)


@pytest.mark.asyncio
async def test_private_channels_excluded_unless_enabled():
    docs = await collect(slack().discover(context()))
    assert all(d.metadata["channel_type"] != "private" for d in docs)

    docs = await collect(slack({"include_private_channels": True}).discover(context()))
    # the default handler returns the same thread/standalone pair for every requested channel
    assert any(d.metadata["channel_id"] == "C2" for d in docs)


@pytest.mark.asyncio
async def test_channel_allowlist_and_excludelist():
    docs = await collect(slack({"channels": ["general"]}).discover(context()))
    assert {d.metadata["channel_id"] for d in docs} == {"C1"}

    docs = await collect(slack({"exclude_channels": ["general"], "include_private_channels": True}).discover(context()))
    assert "C1" not in {d.metadata["channel_id"] for d in docs}


@pytest.mark.asyncio
async def test_channel_allowlist_and_excludelist_also_work_by_channel_id():
    # Slack channel ids are upper-case (e.g. "C1"); the allow/exclude lists must match them
    # case-insensitively just like channel names, not silently fail to match at all.
    docs = await collect(slack({"channels": ["C1"]}).discover(context()))
    assert {d.metadata["channel_id"] for d in docs} == {"C1"}

    docs = await collect(slack({"exclude_channels": ["C1"], "include_private_channels": True}).discover(context()))
    assert "C1" not in {d.metadata["channel_id"] for d in docs}


@pytest.mark.asyncio
async def test_thread_root_and_replies_become_one_document_with_rendered_transcript():
    docs = await collect(slack({"channels": ["general"]}).discover(context()))
    thread = next(d for d in docs if d.external_id == "C1:1700000000.000100")

    assert thread.title == "#general: Hello @Bob B check #secret and [docs](https://example.com) & more"
    assert thread.metadata["reply_count"] == 1
    assert thread.author.name == "Alice"

    content = await slack({"channels": ["general"]}).fetch(thread)
    # mention/channel-ref/link syntax resolved, HTML entity unescaped, reply included with its own line
    assert "@Bob B" in content.text and "#secret" in content.text and "[docs](https://example.com)" in content.text
    assert "& more" in content.text and "reply text" in content.text


@pytest.mark.asyncio
async def test_standalone_messages_with_no_thread_become_their_own_document():
    docs = await collect(slack({"channels": ["general"]}).discover(context()))
    assert any(d.external_id == "C1:1699999999.000000" for d in docs)


@pytest.mark.asyncio
async def test_canonical_url_only_set_when_workspace_domain_configured():
    without = await collect(slack({"channels": ["general"]}).discover(context()))
    assert all(d.canonical_url is None for d in without)

    withdomain = await collect(slack({"channels": ["general"], "workspace_domain": "acme"}).discover(context()))
    thread = next(d for d in withdomain if d.external_id == "C1:1700000000.000100")
    assert thread.canonical_url == "https://acme.slack.com/archives/C1/p1700000000000100"


@pytest.mark.asyncio
async def test_public_channel_has_no_permission_restriction():
    docs = await collect(slack({"channels": ["general"]}).discover(context()))
    thread = docs[0]
    assert await slack().get_permissions(thread) is None


@pytest.mark.asyncio
async def test_private_channel_membership_becomes_permissions():
    docs = await collect(slack({"include_private_channels": True}).discover(context()))
    private_doc = next(d for d in docs if d.metadata["channel_id"] == "C2")
    rules = await slack().get_permissions(private_doc)
    assert {(r.principal_type, r.principal_id) for r in rules} == {("user", "U1"), ("user", "U2")}


@pytest.mark.asyncio
async def test_files_are_indexed_as_their_own_documents_when_enabled():
    file_message = {**STANDALONE, "files": [{"id": "F1", "name": "notes.pdf", "size": 100, "mimetype": "application/pdf", "url_private_download": "https://files.slack.com/F1/notes.pdf", "timestamp": 1700000000}]}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/auth.test"):
            return httpx.Response(200, json={"ok": True, "team": "Acme", "user": "ragbot"})
        if path.endswith("/users.list"):
            return httpx.Response(200, json={"ok": True, "members": USERS, "response_metadata": {"next_cursor": ""}})
        if path.endswith("/conversations.list"):
            return httpx.Response(200, json={"ok": True, "channels": [CHANNELS[0]], "response_metadata": {"next_cursor": ""}})
        if path.endswith("/conversations.history"):
            return httpx.Response(200, json={"ok": True, "messages": [file_message], "response_metadata": {"next_cursor": ""}})
        if "files.slack.com" in str(request.url):
            return httpx.Response(200, content=b"%PDF-1.4")
        return httpx.Response(404)

    connector = slack({"include_files": True}, handler=handler)
    docs = await collect(connector.discover(context()))
    file_doc = next(d for d in docs if d.external_id == "file:C1:F1")
    assert file_doc.parent_external_id == "C1:1699999999.000000"

    content = await connector.fetch(file_doc)
    assert content.file_name == "notes.pdf" and content.data.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_config_and_credential_validation():
    assert (await slack().validate_config()).ok
    assert not (await SlackConnector({}, {}).validate_config()).ok  # bot_token required
