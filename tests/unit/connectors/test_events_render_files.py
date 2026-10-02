"""Webhook payloads, JavaScript rendering, single-item fetches and Teams files."""

from __future__ import annotations

import base64

import httpx
import pytest

from packages.connectors import webhooks
from packages.connectors.sources.confluence import ConfluenceConnector
from packages.connectors.sources.sharepoint import SharePointConnector
from packages.connectors.sources.teams import TeamsConnector
from packages.connectors.sources.web import WebConnector
from packages.connectors.sources.wikipedia import WikipediaConnector
from tests.unit.connectors.helpers import client, collect, context
from tests.unit.connectors.test_graph_connectors import APP, file_item, message, token_response
from tests.unit.connectors.test_wikipedia_confluence import page_item, wiki_handler


# ------------------------------------------------------------------ webhook payloads
def test_only_the_named_items_are_extracted_and_bounded():
    assert webhooks.extract_external_ids("web", {"external_ids": ["a", " b ", "a", 7, ""]}) == ["a", "b", "7"]
    assert len(webhooks.extract_external_ids("web", {"external_ids": [str(i) for i in range(500)]})) == webhooks.MAX_TARGETS
    assert webhooks.extract_external_ids("web", {"external_ids": ["x" * 5000]}) == []  # oversized ids are dropped
    assert webhooks.extract_external_ids("confluence", {"event": "page_updated", "page": {"id": 123}}) == ["123"]
    assert webhooks.extract_external_ids("web", {"page": {"id": 123}}) == []  # Confluence shape only for Confluence
    assert webhooks.extract_external_ids("web", "not a dict") == []
    assert webhooks.extract_external_ids("web", {}) == []


def test_the_secret_is_accepted_in_the_header_or_as_graph_client_state():
    digest = webhooks.secret_hash("s3cret")
    assert webhooks.authenticated(digest, "s3cret", {})
    assert not webhooks.authenticated(digest, "wrong", {})
    assert not webhooks.authenticated(digest, None, {})
    assert not webhooks.authenticated(None, "s3cret", {})  # webhooks not enabled
    assert webhooks.authenticated(digest, None, {"value": [{"clientState": "s3cret"}, {"clientState": "s3cret"}]})
    assert not webhooks.authenticated(digest, None, {"value": [{"clientState": "s3cret"}, {"clientState": "other"}]})  # every notification must carry it
    assert not webhooks.authenticated(digest, None, {"value": [{}]})


def test_only_token_shaped_validation_strings_are_echoed():
    assert webhooks.safe_validation_token("Validation: Testing client application reachability") is None
    assert webhooks.safe_validation_token("abc-123_DEF.ghi") == "abc-123_DEF.ghi"
    assert webhooks.safe_validation_token("<script>alert(1)</script>") is None
    assert webhooks.safe_validation_token(None) is None


# ------------------------------------------------------------------ JavaScript rendering
SHELL = "<html><head><title>App</title></head><body><div id='root'></div><script>render()</script></body></html>"
RENDERED = "<html><head><title>App</title></head><body><main><h1>Dashboard</h1><p>" + "Rendered by the browser after scripts ran. " * 6 + "</p></main></body></html>"


def rendering_site():
    calls = {"render": []}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "renderer":
            calls["render"].append((str(request.url), request.content))
            return httpx.Response(200, text=RENDERED)
        if request.url.path in ("/robots.txt", "/sitemap.xml"):
            return httpx.Response(404)
        return httpx.Response(200, headers={"content-type": "text/html"}, text=SHELL)

    connector = WebConnector(
        {"seed_urls": ["https://app.example.test/"], "max_depth": 0, "javascript_rendering": True, "request_interval_seconds": 0.1},
        http=client(handler, raise_auth_errors=False), allow_private=True,
    )
    connector.render_url = "http://renderer:3000"
    connector._render_http = client(handler, raise_auth_errors=False)
    return connector, calls


@pytest.mark.asyncio
async def test_a_javascript_page_is_indexed_from_the_rendered_html_not_the_empty_shell():
    connector, calls = rendering_site()
    (doc,) = await collect(connector.discover(context()))

    assert "Rendered by the browser" in doc.prefetched.text and "Dashboard" in doc.prefetched.text
    url, body = calls["render"][0]
    assert url == "http://renderer:3000/content" and b"https://app.example.test/" in body


@pytest.mark.asyncio
async def test_without_javascript_rendering_the_shell_yields_nothing_useful():
    connector, calls = rendering_site()
    connector.configuration["javascript_rendering"] = False
    docs = await collect(connector.discover(context()))
    assert calls["render"] == [] and all("Rendered by the browser" not in (d.prefetched.text or "") for d in docs)


@pytest.mark.asyncio
async def test_rendering_needs_the_service_to_be_configured():
    unconfigured = WebConnector({"seed_urls": ["https://app.example.test/"], "javascript_rendering": True})
    unconfigured.render_url = None
    result = await unconfigured.validate_config()
    assert not result.ok and any("CONNECTOR_RENDER_URL" in e for e in result.errors)

    configured = WebConnector({"seed_urls": ["https://app.example.test/"], "javascript_rendering": True})
    configured.render_url = "http://renderer:3000"
    assert (await configured.validate_config()).ok


@pytest.mark.asyncio
async def test_a_failing_renderer_is_reported_per_page_and_the_crawl_continues():
    def handler(request):
        if request.url.host == "renderer":
            return httpx.Response(500)
        if request.url.path in ("/robots.txt", "/sitemap.xml"):
            return httpx.Response(404)
        return httpx.Response(200, headers={"content-type": "text/html"}, text=SHELL)

    connector = WebConnector({"seed_urls": ["https://app.example.test/"], "max_depth": 0, "javascript_rendering": True}, http=client(handler, raise_auth_errors=False), allow_private=True)
    connector.render_url = "http://renderer:3000"
    connector._render_http = client(handler, raise_auth_errors=False, max_retries=0)

    assert await collect(connector.discover(context())) == []
    assert connector.stats["errors"] == 1 and connector.warnings


# ------------------------------------------------------------------ single items (targeted notifications)
@pytest.mark.asyncio
async def test_web_fetches_one_page_or_reports_it_gone():
    def handler(request):
        if request.url.path in ("/robots.txt", "/sitemap.xml"):
            return httpx.Response(404)
        if request.url.path == "/gone":
            return httpx.Response(404)
        return httpx.Response(200, headers={"content-type": "text/html"}, text=RENDERED)

    connector = WebConnector({"seed_urls": ["https://docs.example.test/"]}, http=client(handler, raise_auth_errors=False), allow_private=True)
    doc = await connector.get_external_document("https://docs.example.test/page")
    assert doc.external_id == "https://docs.example.test/page" and doc.prefetched.text
    assert await connector.get_external_document("https://docs.example.test/gone") is None
    assert await connector.get_external_document("https://elsewhere.test/x") is None  # out of scope: not held


@pytest.mark.asyncio
async def test_wikipedia_fetches_one_article_by_id_and_reports_a_missing_one():
    def handler(request):
        if request.url.params.get("pageids") == "999":
            return httpx.Response(200, json={"query": {"pages": [{"pageid": 999, "missing": True}]}})
        return httpx.Response(200, json={"query": {"pages": [{"pageid": 100, "title": "Ada Lovelace", "lastrevid": 5, "revisions": [{"revid": 5, "timestamp": "2026-09-01T10:00:00Z"}], "categories": []}]}})

    connector = WikipediaConnector({"titles": ["x"]}, http=client(handler), allow_private=True)
    doc = await connector.get_external_document("en:100")
    assert (doc.title, doc.external_version) == ("Ada Lovelace", "5")
    assert await connector.get_external_document("en:999") is None


@pytest.mark.asyncio
async def test_confluence_fetches_one_page_applies_the_selection_and_reports_missing_or_trashed():
    def handler(request):
        path = request.url.path
        if path.endswith("/content/404"):
            return httpx.Response(404)
        if path.endswith("/content/9"):
            return httpx.Response(200, json={**page_item(9), "status": "trashed"})
        if path.endswith("/content/5"):
            return httpx.Response(200, json={**page_item(5, space="OPS"), "status": "current"})
        return httpx.Response(200, json={**page_item(1), "status": "current"})

    connector = ConfluenceConnector({"base_url": "https://corp.atlassian.net/wiki", "spaces": ["ENG"]}, {"api_token": "t"}, http=client(handler), allow_private=True)
    assert (await connector.get_external_document("1")).metadata["page_id"] == "1"
    assert await connector.get_external_document("404") is None
    assert await connector.get_external_document("9") is None  # trashed
    assert await connector.get_external_document("5") is None  # a space that is not selected
    with pytest.raises(NotImplementedError):
        await connector.get_external_document("att:1")  # attachments are refreshed with their page


@pytest.mark.asyncio
async def test_sharepoint_fetches_one_file_and_reports_deleted_or_out_of_selection():
    def handler(request):
        path = request.url.path
        if "oauth2/v2.0/token" in path:
            return token_response()
        if path.endswith("/sites/contoso.sharepoint.com:/sites/Eng"):
            return httpx.Response(200, json={"id": "site-1"})
        if path.endswith("/sites/site-1/drives"):
            return httpx.Response(200, json={"value": [{"id": "drive-1", "name": "Documents", "driveType": "documentLibrary"}]})
        if path.endswith("/items/f1"):
            return httpx.Response(200, json=file_item("f1"))
        if path.endswith("/items/f2"):
            return httpx.Response(200, json={"id": "f2", "deleted": {"state": "deleted"}})
        if path.endswith("/items/f3"):
            return httpx.Response(200, json=file_item("f3", "Photo.png"))
        return httpx.Response(404)

    connector = SharePointConnector({"site_url": "https://contoso.sharepoint.com/sites/Eng"}, APP, http=client(handler), allow_private=True)
    assert (await connector.get_external_document("drive-1:f1")).title == "Policy.docx"
    assert await connector.get_external_document("drive-1:f2") is None
    assert await connector.get_external_document("drive-1:f3") is None  # not a supported type
    assert await connector.get_external_document("drive-1:missing") is None


# ------------------------------------------------------------------ Teams files and single threads
def teams_with_files():
    calls = []
    shared_url = "https://contoso.sharepoint.com/sites/eng/Shared%20Documents/runbook.docx"

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if "oauth2/v2.0/token" in path:
            return token_response()
        if path.endswith("/teams/11111111-1111-1111-1111-111111111111"):
            return httpx.Response(200, json={"id": "11111111-1111-1111-1111-111111111111", "displayName": "Engineering"})
        if path.endswith("/channels"):
            return httpx.Response(200, json={"value": [{"id": "c1", "displayName": "Backend", "membershipType": "standard"}]})
        if path.endswith("/channels/c1/messages"):
            root = message("m1", "See the attached runbook", subject="Runbook")
            root["attachments"] = [
                {"id": "a1", "contentType": "reference", "contentUrl": shared_url, "name": "runbook.docx"},
                {"id": "a2", "contentType": "reference", "contentUrl": shared_url + "?dup", "name": "notes.png"},  # not a supported type
            ]
            return httpx.Response(200, json={"value": [root]})
        if path.endswith("/replies"):
            reply = message("r1", "Same file again", created="2026-09-25T08:30:00Z")
            reply["attachments"] = [{"id": "a3", "contentType": "reference", "contentUrl": shared_url, "name": "runbook.docx"}]
            return httpx.Response(200, json={"value": [reply]})
        if "/shares/" in path and path.endswith("/driveItem"):
            return httpx.Response(200, json={**file_item("f9", "runbook.docx"), "parentReference": {"driveId": "drive-7", "path": "/drive/root:/Shared Documents"}})
        if path.endswith("/drives/drive-7/items/f9/content"):
            return httpx.Response(200, content=b"DOCX")
        return httpx.Response(404)

    connector = TeamsConnector(
        {"teams": ["11111111-1111-1111-1111-111111111111"], "include_files": True, "history_days": 3650}, APP, http=client(handler), allow_private=True,
    )
    connector.calls = calls  # type: ignore[attr-defined]
    return connector, shared_url


@pytest.mark.asyncio
async def test_files_shared_in_a_thread_become_documents_with_the_channels_access():
    connector, shared_url = teams_with_files()
    docs = await collect(connector.discover(context()))

    files = [d for d in docs if d.external_id.startswith("file:")]
    assert [f.external_id for f in files] == ["file:drive-7:f9"]  # de-duplicated across root and reply; the .png is skipped
    (file_doc,) = files
    assert file_doc.title == "runbook.docx" and file_doc.parent_external_id.endswith(":m1")
    assert (file_doc.metadata["team_name"], file_doc.metadata["channel_name"]) == ("Engineering", "Backend")

    expected = "u!" + base64.urlsafe_b64encode(shared_url.encode()).decode().rstrip("=")
    assert any(f"/shares/{expected}/driveItem" in c.url.path for c in connector.calls)  # resolved through the shares API

    content = await connector.fetch(file_doc)
    assert content.data == b"DOCX" and content.file_name == "runbook.docx"


@pytest.mark.asyncio
async def test_files_are_not_read_unless_enabled():
    connector, _ = teams_with_files()
    connector.configuration["include_files"] = False
    docs = await collect(connector.discover(context()))
    assert not any(d.external_id.startswith("file:") for d in docs)
    assert not any("/shares/" in c.url.path for c in connector.calls)  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_a_file_the_service_cannot_read_does_not_stop_the_thread_being_indexed():
    connector, _ = teams_with_files()
    original = connector.http._client._transport.handler  # type: ignore[attr-defined]

    def deny_shares(request):
        return httpx.Response(403) if "/shares/" in request.url.path else original(request)

    connector.http._client._transport.handler = deny_shares  # type: ignore[attr-defined]
    docs = await collect(connector.discover(context()))
    assert [d.external_id for d in docs] == ["11111111-1111-1111-1111-111111111111:c1:m1"]


@pytest.mark.asyncio
async def test_teams_fetches_one_thread_by_id_and_reports_deleted_or_disallowed_ones():
    def handler(request):
        path = request.url.path
        if "oauth2/v2.0/token" in path:
            return token_response()
        if path.endswith("/messages/gone"):
            return httpx.Response(404)
        if path.endswith("/messages/m1/replies"):
            return httpx.Response(200, json={"value": [message("r1", "answer", created="2026-09-25T08:30:00Z")]})
        if "/messages/m1" in path:
            return httpx.Response(200, json=message("m1", "question", subject="Q"))
        if path.endswith("/channels/c1"):
            return httpx.Response(200, json={"id": "c1", "displayName": "Backend", "membershipType": "standard"})
        if path.endswith("/channels/cp"):
            return httpx.Response(200, json={"id": "cp", "displayName": "Leadership", "membershipType": "private"})
        if "/messages/mp" in path:
            return httpx.Response(200, json=message("mp", "secret"))
        if path.endswith("/teams/11111111-1111-1111-1111-111111111111"):
            return httpx.Response(200, json={"id": "11111111-1111-1111-1111-111111111111", "displayName": "Engineering"})
        return httpx.Response(404)

    team = "11111111-1111-1111-1111-111111111111"
    connector = TeamsConnector({"teams": [team]}, APP, http=client(handler), allow_private=True)
    doc = await connector.get_external_document(f"{team}:c1:m1")
    assert doc.title == "Engineering / Backend: Q" and doc.metadata["reply_count"] == 1
    assert await connector.get_external_document(f"{team}:c1:gone") is None
    assert await connector.get_external_document(f"{team}:cp:mp") is None  # a private channel that is not enabled
    assert await connector.get_external_document("not-a-valid-id") is None
