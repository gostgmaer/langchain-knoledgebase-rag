from __future__ import annotations

import httpx
import pytest

from packages.connectors.http import AuthenticationFailed
from packages.connectors.models import ExternalDocument
from packages.connectors.sources.sharepoint import OneDriveConnector, SharePointConnector
from packages.connectors.sources.teams import TeamsConnector
from tests.unit.connectors.helpers import client, collect, context

APP = {"tenant_id": "tenant-1", "client_id": "client-1", "client_secret": "SECRET"}


def token_response():
    return httpx.Response(200, json={"access_token": "graph-token", "expires_in": 3600})


def file_item(item_id, name="Policy.docx", *, etag="e1", folder="/drive/root:/Product Documentation", size=1000):
    return {
        "id": item_id, "name": name, "eTag": etag, "size": size, "webUrl": f"https://contoso.sharepoint.com/{name}",
        "lastModifiedDateTime": "2026-09-20T09:00:00Z", "createdDateTime": "2026-01-01T00:00:00Z",
        "createdBy": {"user": {"id": "u1", "displayName": "Dana", "email": "dana@contoso.test"}},
        "parentReference": {"id": "folder-1", "path": folder},
        "file": {"mimeType": "application/octet-stream", "hashes": {"sha1Hash": "abc"}},
    }


# ------------------------------------------------------------------ SharePoint
def sharepoint(config=None, *, delta_pages=None, deletions=(), state_tokens=None, credentials=None):
    calls = []
    delta_pages = delta_pages or [[file_item("f1"), file_item("f2", "Notes.txt"), file_item("f3", "Photo.png"), {"id": "d1", "name": "Sub", "folder": {}}]]

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        url = str(request.url)
        path = request.url.path
        if "oauth2/v2.0/token" in path:
            return token_response()
        if path.endswith("/organization"):
            return httpx.Response(200, json={"value": [{"displayName": "Contoso"}]})
        if path.endswith("/sites/contoso.sharepoint.com:/sites/Eng"):
            return httpx.Response(200, json={"id": "site-1"})
        if path.endswith("/sites/site-1/drives"):
            return httpx.Response(200, json={"value": [{"id": "drive-1", "name": "Documents", "driveType": "documentLibrary"}, {"id": "drive-2", "name": "Other", "driveType": "documentLibrary"}]})
        if path.endswith("/drives/drive-1/root/delta") or "token=" in url:
            token = request.url.params.get("token")
            if token == "T1":  # resumed with a saved delta token: only changes
                value = [file_item("f1", etag="e2"), {"id": "f2", "deleted": {}}]
                return httpx.Response(200, json={"value": value, "@odata.deltaLink": "https://graph.microsoft.com/v1.0/drives/drive-1/root/delta?token=T2"})
            value = delta_pages[0]
            return httpx.Response(200, json={"value": value, "@odata.deltaLink": "https://graph.microsoft.com/v1.0/drives/drive-1/root/delta?token=T1"})
        if path.endswith("/items/f1/permissions"):
            return httpx.Response(200, json={"value": [
                {"roles": ["read"], "grantedToV2": {"user": {"email": "sam@contoso.test", "displayName": "Sam"}}},
                {"roles": ["write"], "grantedToIdentitiesV2": [{"group": {"id": "grp-1", "displayName": "Engineering"}}]},
                {"roles": ["read"], "link": {"scope": "organization"}},
            ]})
        if path.endswith("/items/f1/content"):
            return httpx.Response(200, content=b"DOCX-BYTES")
        return httpx.Response(404)

    connector = SharePointConnector(
        {"site_url": "https://contoso.sharepoint.com/sites/Eng", "libraries": ["Documents"], **(config or {})},
        credentials or APP,
        http=client(handler),
        allow_private=True,
    )
    connector.calls = calls  # type: ignore[attr-defined]
    return connector


@pytest.mark.asyncio
async def test_sharepoint_lists_supported_files_only_with_full_metadata_and_saves_the_delta_token():
    connector = sharepoint()
    ctx = context()
    docs = await collect(connector.discover(ctx))

    assert [d.title for d in docs] == ["Policy.docx", "Notes.txt"]  # folder and .png are not documents
    policy = docs[0]
    assert policy.external_id == "drive-1:f1" and policy.external_version == "e1"
    assert policy.canonical_url == "https://contoso.sharepoint.com/Policy.docx"
    m = policy.metadata
    assert (m["file_id"], m["folder"], m["path"], m["owner"], m["library"]) == ("f1", "Product Documentation", "Product Documentation/Policy.docx", "Dana", "Documents")
    assert ctx.state["delta"] == {"drive-1": "https://graph.microsoft.com/v1.0/drives/drive-1/root/delta?token=T1"}


@pytest.mark.asyncio
async def test_sharepoint_incremental_sync_uses_the_delta_token_and_reports_deletions():
    connector = sharepoint()
    ctx = context(state={"delta": {"drive-1": "https://graph.microsoft.com/v1.0/drives/drive-1/root/delta?token=T1"}})

    changes = await connector.get_changes(ctx)

    assert {(c.kind, c.external_id) for c in changes} == {("updated", "drive-1:f1"), ("deleted", "drive-1:f2")}
    assert next(c for c in changes if c.kind == "updated").document.external_version == "e2"
    assert ctx.state["delta"]["drive-1"].endswith("token=T2")  # the next run continues from here


@pytest.mark.asyncio
async def test_sharepoint_without_a_saved_token_asks_for_a_full_pass():
    assert await sharepoint().get_changes(context()) is None


@pytest.mark.asyncio
async def test_sharepoint_folder_extension_size_and_pattern_filters():
    pages = [[
        file_item("f1", "A.docx", folder="/drive/root:/Product Documentation"),
        file_item("f2", "B.docx", folder="/drive/root:/HR"),
        file_item("f3", "C.docx", folder="/drive/root:/Product Documentation/Archive"),
        file_item("f4", "Big.pdf", folder="/drive/root:/Product Documentation", size=50 * 1024 * 1024),
    ]]
    connector = sharepoint({"folders": ["Product Documentation"], "exclude_patterns": ["*/archive/*"]}, delta_pages=pages)
    assert [d.title for d in await collect(connector.discover(context()))] == ["A.docx"]


@pytest.mark.asyncio
async def test_sharepoint_permissions_map_users_groups_and_org_links():
    connector = sharepoint()
    doc = (await collect(connector.discover(context())))[0]
    rules = await connector.get_permissions(doc)
    assert {(r.principal_type, r.principal_id, r.permission) for r in rules} == {
        ("user", "sam@contoso.test", "read"),
        ("group", "grp-1", "write"),
        ("group", "organization", "read"),
    }


@pytest.mark.asyncio
async def test_sharepoint_fetch_returns_bytes_for_the_existing_loaders():
    connector = sharepoint()
    doc = (await collect(connector.discover(context())))[0]
    content = await connector.fetch(doc)
    assert content.data == b"DOCX-BYTES" and content.file_name == "Policy.docx" and content.content_hash


@pytest.mark.asyncio
async def test_graph_token_is_cached_and_the_secret_never_appears_in_a_url_or_header():
    connector = sharepoint()
    await collect(connector.discover(context()))
    token_calls = [c for c in connector.calls if "oauth2/v2.0/token" in c.url.path]
    assert len(token_calls) == 1
    for call in connector.calls:
        assert "SECRET" not in str(call.url)
        assert "SECRET" not in call.headers.get("authorization", "")


@pytest.mark.asyncio
async def test_graph_expired_token_is_refreshed_once_then_reported():
    state = {"tokens": 0}

    def handler(request):
        if "oauth2/v2.0/token" in request.url.path:
            state["tokens"] += 1
            return token_response()
        return httpx.Response(401)

    connector = SharePointConnector({"site_url": "https://contoso.sharepoint.com/sites/Eng"}, APP, http=client(handler), allow_private=True)
    with pytest.raises(AuthenticationFailed):
        await connector.graph_get("/organization")
    assert state["tokens"] == 2  # the cached token was refreshed once, then the failure surfaced


@pytest.mark.asyncio
async def test_graph_invalid_client_secret_is_a_clear_authentication_error():
    def handler(request):
        return httpx.Response(401, json={"error": "invalid_client", "error_description": "AADSTS7000215: Invalid client secret SECRET"})

    connector = SharePointConnector({"site_url": "https://contoso.sharepoint.com/sites/Eng"}, APP, http=client(handler), allow_private=True)
    result = await connector.test_connection()
    assert not result.ok and result.authenticated is False
    assert "SECRET" not in result.message and "invalid_client" in result.message


@pytest.mark.asyncio
async def test_graph_credential_validation_accepts_either_form():
    site = {"site_url": "https://contoso.sharepoint.com/sites/Eng"}
    assert (await SharePointConnector(site, APP).validate_config()).ok
    assert (await SharePointConnector(site, {"access_token": "t"}).validate_config()).ok
    partial = await SharePointConnector(site, {"tenant_id": "t"}).validate_config()
    assert not partial.ok
    assert not (await SharePointConnector(site, {}).validate_config()).ok


@pytest.mark.asyncio
async def test_onedrive_reads_the_named_users_drive():
    def handler(request):
        path = request.url.path
        if "oauth2/v2.0/token" in path:
            return token_response()
        if path.endswith("/users/alex@contoso.test/drive"):
            return httpx.Response(200, json={"id": "drive-9", "name": "OneDrive"})
        if path.endswith("/drives/drive-9/root/delta"):
            return httpx.Response(200, json={"value": [file_item("x1", "Mine.pdf", folder="/drive/root:/Docs")], "@odata.deltaLink": "https://graph.microsoft.com/v1.0/drives/drive-9/root/delta?token=Z"})
        return httpx.Response(404)

    connector = OneDriveConnector({"user": "alex@contoso.test"}, APP, http=client(handler), allow_private=True)
    assert (await connector.validate_config()).ok
    docs = await collect(connector.discover(context()))
    assert [d.external_id for d in docs] == ["drive-9:x1"]


# ------------------------------------------------------------------ Teams
def message(msg_id, text, author="Dana", created="2026-09-24T10:00:00Z", **extra):
    return {
        "id": msg_id, "messageType": "message", "createdDateTime": created, "lastModifiedDateTime": created,
        "from": {"user": {"id": "u1", "displayName": author}}, "body": {"contentType": "html", "content": f"<p>{text}</p>"},
        "webUrl": f"https://teams.microsoft.com/l/message/{msg_id}", **extra,
    }


def teams(config=None):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if "oauth2/v2.0/token" in path:
            return token_response()
        if path.endswith("/organization"):
            return httpx.Response(200, json={"value": [{"displayName": "Contoso"}]})
        if path.endswith("/teams/11111111-1111-1111-1111-111111111111"):
            return httpx.Response(200, json={"id": "11111111-1111-1111-1111-111111111111", "displayName": "Engineering"})
        if path.endswith("/channels"):
            return httpx.Response(200, json={"value": [
                {"id": "c1", "displayName": "Backend", "membershipType": "standard"},
                {"id": "c2", "displayName": "Architecture", "membershipType": "standard"},
                {"id": "c3", "displayName": "Leadership", "membershipType": "private"},
            ]})
        if path.endswith("/channels/c1/messages"):
            return httpx.Response(200, json={"value": [
                message("m1", "How do we rotate the signing key?", subject="Key rotation"),
                message("m2", "Old thread", created="2020-01-01T00:00:00Z"),
                {**message("m3", "deleted"), "deletedDateTime": "2026-09-01T00:00:00Z"},
                {**message("m4", "joined"), "messageType": "systemEventMessage"},
            ]})
        if path.endswith("/replies") and "/messages/m1/" not in path:
            return httpx.Response(200, json={"value": []})
        if path.endswith("/messages/m1/replies"):
            return httpx.Response(200, json={"value": [message("r1", "Every 90 days, see the runbook.", author="Sam", created="2026-09-25T08:30:00Z")]})
        if path.endswith(("/channels/c2/messages", "/channels/c3/messages")):
            return httpx.Response(200, json={"value": []})
        if path.endswith("/teams/11111111-1111-1111-1111-111111111111/members"):
            return httpx.Response(200, json={"value": [{"userId": "u1", "email": "dana@contoso.test", "displayName": "Dana", "roles": ["owner"]}, {"userId": "u2", "email": "sam@contoso.test", "displayName": "Sam", "roles": []}]})
        return httpx.Response(404)

    connector = TeamsConnector(
        {"teams": ["11111111-1111-1111-1111-111111111111"], "history_days": 90, **(config or {})},
        APP, http=client(handler), allow_private=True,
    )
    connector.calls = calls  # type: ignore[attr-defined]
    return connector


@pytest.mark.asyncio
async def test_teams_threads_become_readable_transcripts_with_provenance_metadata():
    connector = teams({"history_days": 3650})
    docs = await collect(connector.discover(context()))

    thread = next(d for d in docs if d.metadata["message_id"] == "m1")
    assert thread.title == "Engineering / Backend: Key rotation"
    assert thread.external_id == "11111111-1111-1111-1111-111111111111:c1:m1"
    m = thread.metadata
    assert (m["team_name"], m["channel_name"], m["thread_id"], m["author"], m["reply_count"]) == ("Engineering", "Backend", "m1", "Dana", 1)
    assert thread.canonical_url == "https://teams.microsoft.com/l/message/m1"
    text = thread.prefetched.text
    assert "How do we rotate the signing key?" in text and "(reply)" in text and "Every 90 days" in text
    assert thread.external_version.endswith("|1")  # a new reply changes the version -> the thread is re-indexed


@pytest.mark.asyncio
async def test_teams_deleted_system_and_out_of_window_messages_are_skipped():
    docs = await collect(teams().discover(context()))
    ids = {d.metadata["message_id"] for d in docs}
    assert ids == {"m1"}  # m2 is older than the window, m3 deleted, m4 a system event


@pytest.mark.asyncio
async def test_teams_private_channels_are_only_read_when_enabled_and_channel_filter_applies():
    default = teams()
    await collect(default.discover(context()))
    assert not any("/channels/c3/" in c.url.path for c in default.calls)

    enabled = teams({"include_private_channels": True})
    await collect(enabled.discover(context()))
    assert any("/channels/c3/messages" in c.url.path for c in enabled.calls)

    only = teams({"channels": ["Architecture"]})
    await collect(only.discover(context()))
    assert not any("/channels/c1/messages" in c.url.path for c in only.calls)


@pytest.mark.asyncio
async def test_teams_never_touches_chats():
    connector = teams({"include_private_channels": True})
    await collect(connector.discover(context()))
    assert not any("/chats" in c.url.path for c in connector.calls)


@pytest.mark.asyncio
async def test_teams_permissions_are_the_team_membership():
    connector = teams({"history_days": 3650})
    doc = (await collect(connector.discover(context())))[0]
    rules = await connector.get_permissions(doc)
    assert {(r.principal_id, r.permission) for r in rules} == {("dana@contoso.test", "admin"), ("sam@contoso.test", "read")}


@pytest.mark.asyncio
async def test_teams_config_requires_at_least_one_team_and_test_connection_lists_scope():
    assert not (await TeamsConnector({}, APP).validate_config()).ok
    result = await teams().test_connection()
    assert result.ok and result.details["teams"] == ["Engineering"]
