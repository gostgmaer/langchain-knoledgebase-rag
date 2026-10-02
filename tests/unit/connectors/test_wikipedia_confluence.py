from __future__ import annotations

import httpx
import pytest

from packages.connectors.http import AuthenticationFailed
from packages.connectors.models import ExternalDocument
from packages.connectors.sources.confluence import ConfluenceConnector
from packages.connectors.sources.wikipedia import WikipediaConnector, parse_article_url
from tests.unit.connectors.helpers import client, collect, context


# ------------------------------------------------------------------ Wikipedia
def wiki_handler(request: httpx.Request) -> httpx.Response:
    q = dict(request.url.params)
    assert "EasyDevRAGBot" in request.headers["user-agent"]  # Wikimedia policy: descriptive User-Agent
    if q.get("meta") == "siteinfo":
        return httpx.Response(200, json={"query": {"general": {"sitename": "Wikipedia", "generator": "MediaWiki 1.43"}}})
    if q.get("list") == "categorymembers":
        return httpx.Response(200, json={"query": {"categorymembers": [{"title": "Ada Lovelace"}, {"title": "Grace Hopper"}]}})
    if "titles" in q:
        pages = []
        for i, title in enumerate(q["titles"].split("|")):
            if title == "Nonexistent":
                pages.append({"title": title, "missing": True})
                continue
            pages.append({
                "pageid": 100 + i, "title": title, "canonicalurl": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                "lastrevid": 5000 + i, "revisions": [{"revid": 5000 + i, "timestamp": "2026-09-01T10:00:00Z"}],
                "categories": [{"title": "Category:Mathematicians"}],
            })
        return httpx.Response(200, json={"query": {"pages": pages}})
    if q.get("prop") == "extracts":
        return httpx.Response(200, json={"query": {"pages": [{"pageid": int(q["pageids"]), "title": "X", "extract": "Intro text.\n\n== History ==\nOld times.\n\n=== Early ===\nEven older."}]}})
    return httpx.Response(400)


def wiki(config) -> WikipediaConnector:
    return WikipediaConnector(config, http=client(wiki_handler), allow_private=True)


def test_article_urls_are_parsed_and_non_wikipedia_urls_rejected():
    assert parse_article_url("https://en.wikipedia.org/wiki/Alan_Turing") == ("en", "Alan Turing")
    assert parse_article_url("https://de.wikipedia.org/wiki/K%C3%B6ln") == ("de", "Köln")
    assert parse_article_url("https://evil.test/wiki/Alan_Turing") is None
    assert parse_article_url("https://en.wikipedia.org/w/index.php?title=X") is None


@pytest.mark.asyncio
async def test_wikipedia_discovery_captures_revision_metadata_and_skips_missing_articles():
    connector = wiki({"titles": ["Alan Turing", "Nonexistent"], "article_urls": ["https://fr.wikipedia.org/wiki/Paris"]})
    docs = await collect(connector.discover(context()))

    by_title = {d.title: d for d in docs}
    assert set(by_title) == {"Alan Turing", "Paris"}
    turing = by_title["Alan Turing"]
    assert turing.external_version == "5000"  # the revision id is the version
    assert turing.canonical_url == "https://en.wikipedia.org/wiki/Alan_Turing"
    assert turing.metadata["revision_id"] == 5000 and turing.metadata["language"] == "en"
    assert turing.metadata["categories"] == ["Mathematicians"]
    assert by_title["Paris"].metadata["language"] == "fr"


@pytest.mark.asyncio
async def test_wikipedia_categories_are_expanded_and_capped():
    connector = wiki({"categories": ["Computer scientists"], "max_articles": 1})
    assert len(await collect(connector.discover(context()))) == 1


@pytest.mark.asyncio
async def test_wikipedia_content_is_converted_to_markdown_headings():
    connector = wiki({"titles": ["Alan Turing"]})
    doc = (await collect(connector.discover(context())))[0]
    text = (await connector.fetch(doc)).text
    assert text.startswith("# Alan Turing")
    assert "## History" in text and "### Early" in text


@pytest.mark.asyncio
async def test_wikipedia_validation_and_connection_test():
    assert not (await wiki({"language": "not a code!", "titles": ["A"]}).validate_config()).ok
    assert not (await wiki({}).validate_config()).ok
    assert not (await wiki({"article_urls": ["https://evil.test/wiki/X"]}).validate_config()).ok
    assert (await wiki({"titles": ["A"]}).validate_config()).ok
    assert (await wiki({"titles": ["A"]}).test_connection()).ok


# ------------------------------------------------------------------ Confluence
def page_item(i, *, space="ENG", space_type="global", version=3, ancestors=()):
    return {
        "id": str(i), "type": "page", "title": f"Page {i}",
        "space": {"key": space, "name": f"{space} space", "type": space_type},
        "version": {"number": version, "when": "2026-09-20T09:00:00.000Z", "by": {"accountId": "acc-1", "displayName": "Dana", "email": "dana@corp.test"}},
        "history": {"createdDate": "2026-01-01T00:00:00.000Z"},
        "ancestors": [{"id": str(a), "title": f"Parent {a}"} for a in ancestors],
        "metadata": {"labels": {"results": [{"name": "policy"}]}},
        "_links": {"webui": f"/spaces/{space}/pages/{i}", "base": "https://corp.atlassian.net/wiki"},
    }


def confluence(config=None, handler=None, credentials=None):
    calls = []

    def default(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path.endswith("/rest/api/space"):
            return httpx.Response(200, json={"size": 2})
        if path.endswith("/rest/api/content/search"):
            if request.url.params.get("start") == "1":
                return httpx.Response(200, json={"results": [page_item(3, space="~dana", space_type="personal")], "_links": {}})
            return httpx.Response(200, json={
                "results": [page_item(1, ancestors=(9,)), page_item(2, version=7)],
                "_links": {"next": "/rest/api/content/search?cql=x&start=1&limit=50", "base": "https://corp.atlassian.net/wiki"},
            })
        if "/content/" in path and path.endswith("/restriction/byOperation/read"):
            return httpx.Response(200, json={"restrictions": {"user": {"results": [{"accountId": "acc-9", "displayName": "Sam"}]}, "group": {"results": [{"name": "eng-leads"}]}}})
        if "/content/" in path:
            return httpx.Response(200, json={"body": {"view": {"value": "<h2>Leave</h2><p>25 days.</p>"}}})
        return httpx.Response(404)

    connector = ConfluenceConnector(
        {"base_url": "https://corp.atlassian.net/wiki", **(config or {})},
        credentials or {"email": "svc@corp.test", "api_token": "TOKEN"},
        http=client(handler or default, min_interval=0.0),
        allow_private=True,
    )
    connector.calls = calls  # type: ignore[attr-defined]
    return connector


@pytest.mark.asyncio
async def test_confluence_pages_are_mapped_with_full_provenance_metadata():
    connector = confluence()
    docs = await collect(connector.discover(context()))

    page = next(d for d in docs if d.external_id == "1")
    assert page.canonical_url == "https://corp.atlassian.net/wiki/spaces/ENG/pages/1"  # the original URL, for citations
    assert page.external_version == "3"
    assert page.parent_external_id == "9"
    assert page.author.name == "Dana"
    m = page.metadata
    assert (m["space_key"], m["page_id"], m["parent_page_id"], m["version"], m["labels"]) == ("ENG", "1", "9", 3, ["policy"])


@pytest.mark.asyncio
async def test_confluence_personal_spaces_are_excluded_unless_enabled_and_paging_is_followed():
    docs = await collect(confluence().discover(context()))
    assert sorted(d.external_id for d in docs) == ["1", "2"]

    docs = await collect(confluence({"include_personal_spaces": True}).discover(context()))
    assert sorted(d.external_id for d in docs) == ["1", "2", "3"]


@pytest.mark.asyncio
async def test_confluence_selection_is_pushed_into_the_cql_query():
    connector = confluence({"spaces": ["ENG", "HR"], "exclude_spaces": ["OLD"], "labels": ["policy"], "parent_page_ids": ["42"]})
    await collect(connector.discover(context()))
    cql = connector.calls[0].url.params["cql"]
    assert 'space in ("ENG","HR")' in cql and 'space not in ("OLD")' in cql
    assert 'label in ("policy")' in cql and 'ancestor in ("42")' in cql
    assert "status = current" in cql  # archived content is excluded by default

    archived = confluence({"include_archived": True})
    await collect(archived.discover(context()))
    assert "status = current" not in archived.calls[0].url.params["cql"]


@pytest.mark.asyncio
async def test_confluence_content_is_rendered_to_markdown_and_credentials_go_in_the_header_only():
    connector = confluence()
    doc = (await collect(connector.discover(context())))[0]
    text = (await connector.fetch(doc)).text
    assert "## Leave" in text and "25 days." in text

    request = connector.calls[-1]
    assert request.headers["authorization"].startswith("Basic ")
    assert "TOKEN" not in str(request.url)


@pytest.mark.asyncio
async def test_confluence_personal_access_token_uses_bearer():
    connector = confluence(credentials={"api_token": "PAT"})
    await connector.test_connection()
    assert connector.calls[-1].headers["authorization"] == "Bearer PAT"


@pytest.mark.asyncio
async def test_confluence_page_restrictions_become_permissions():
    connector = confluence()
    doc = (await collect(connector.discover(context())))[0]
    rules = await connector.get_permissions(doc)
    assert {(r.principal_type, r.principal_id) for r in rules} == {("user", "acc-9"), ("group", "eng-leads")}


@pytest.mark.asyncio
async def test_confluence_bad_credentials_are_reported_not_raised_by_test_connection():
    connector = confluence(handler=lambda request: httpx.Response(401))
    result = await connector.test_connection()
    assert not result.ok and result.authenticated is False
    with pytest.raises(AuthenticationFailed):
        await collect(connector.discover(context()))


@pytest.mark.asyncio
async def test_confluence_attachments_are_indexed_as_their_own_documents():
    def handler(request):
        path = request.url.path
        if path.endswith("/rest/api/content/search"):
            return httpx.Response(200, json={"results": [page_item(1)], "_links": {}})
        if path.endswith("/child/attachment"):
            return httpx.Response(200, json={"results": [
                {"id": "att9", "title": "policy.pdf", "metadata": {"mediaType": "application/pdf"}, "version": {"number": 2}, "_links": {"download": "/download/attachments/1/policy.pdf", "base": "https://corp.atlassian.net/wiki"}},
                {"id": "att10", "title": "logo.png", "metadata": {"mediaType": "image/png"}, "version": {"number": 1}, "_links": {}},
            ]})
        if "/download/attachments/" in path:
            return httpx.Response(200, content=b"%PDF-1.4")
        return httpx.Response(404)

    connector = confluence({"include_attachments": True}, handler=handler)
    docs = await collect(connector.discover(context()))
    attachment = next(d for d in docs if d.external_id == "att:att9")
    assert attachment.parent_external_id == "1" and not any(d.external_id == "att:att10" for d in docs)
    content = await connector.fetch(attachment)
    assert content.file_name == "policy.pdf" and content.data.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_confluence_config_and_credential_validation():
    ok = await ConfluenceConnector({"base_url": "https://corp.atlassian.net/wiki"}, {"api_token": "t"}).validate_config()
    assert ok.ok
    assert not (await ConfluenceConnector({"base_url": "https://corp.atlassian.net/wiki"}, {}).validate_config()).ok
    assert not (await ConfluenceConnector({"base_url": "not a url"}, {"api_token": "t"}).validate_config()).ok
    assert not (await ConfluenceConnector({"base_url": "https://x.test", "content_types": ["comment"]}, {"api_token": "t"}).validate_config()).ok
