from __future__ import annotations

import httpx
import pytest

from packages.connectors.models import KnownDocument
from packages.connectors.sources.web import WebConnector, normalize_url
from tests.unit.connectors.helpers import client, collect, context

BODY = "<p>" + "Some real documentation text that is long enough. " * 8 + "</p>"
HTML = {"content-type": "text/html; charset=utf-8"}


def page(title, links=(), canonical=None, extra=""):
    anchors = "".join(f'<a href="{link}">link</a>' for link in links)
    canon = f'<link rel="canonical" href="{canonical}">' if canonical else ""
    return f"<html><head><title>{title}</title>{canon}</head><body><main><h1>{title}</h1>{BODY}{anchors}{extra}</main></body></html>"


SITE = {
    "/": page("Home", ["/docs/a", "/docs/b", "/admin/panel", "https://other.test/x", "/docs/a?utm_source=x", "/file.zip"]),
    "/docs/a": page("A", ["/docs/deep"]),
    "/docs/b": page("B"),
    "/docs/deep": page("Deep"),
    "/admin/panel": page("Admin"),
}


def make(pages=SITE, robots="User-agent: *\nDisallow: /private/\n", extra_config=None, **client_kwargs):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        seen.append(str(request.url))
        if path == "/robots.txt":
            return httpx.Response(200, text=robots) if robots is not None else httpx.Response(404)
        if path == "/sitemap.xml":
            return httpx.Response(404)
        if path == "/file.zip":
            return httpx.Response(200, headers={"content-type": "application/zip"}, content=b"PK")
        if path in pages:
            return httpx.Response(200, headers={**HTML, "etag": f'"{path}"'}, text=pages[path])
        return httpx.Response(404)

    http = client(handler, raise_auth_errors=False, **client_kwargs)
    config = {"seed_urls": ["https://docs.example.test/"], "max_depth": 3, "max_pages": 50, "request_interval_seconds": 0.1}
    config.update(extra_config or {})
    return WebConnector(config, http=http, allow_private=True), seen


@pytest.mark.asyncio
async def test_crawl_follows_links_within_scope_and_collapses_tracking_duplicates():
    connector, seen = make(extra_config={"exclude_patterns": ["docs.example.test/admin/*"]})
    docs = await collect(connector.discover(context()))

    assert sorted(d.external_id for d in docs) == [
        "https://docs.example.test/",
        "https://docs.example.test/docs/a",
        "https://docs.example.test/docs/b",
        "https://docs.example.test/docs/deep",
    ]
    assert not any("other.test" in u for u in seen)  # off-domain never requested
    assert not any("/admin/" in u for u in seen)  # excluded pattern never requested
    assert connector.stats["skipped_out_of_scope"] >= 1


@pytest.mark.asyncio
async def test_depth_limit_and_page_limit_are_enforced():
    connector, _ = make(extra_config={"max_depth": 1})
    ids = {d.external_id for d in await collect(connector.discover(context()))}
    assert "https://docs.example.test/docs/deep" not in ids  # depth 2

    connector, _ = make(extra_config={"max_pages": 2})
    assert len(await collect(connector.discover(context()))) == 2


@pytest.mark.asyncio
async def test_robots_txt_disallow_is_respected_and_can_be_overridden_for_own_sites():
    pages = {**SITE, "/private/x": page("Secret"), "/": page("Home", ["/private/x", "/docs/a"])}
    connector, seen = make(pages)
    ids = {d.external_id for d in await collect(connector.discover(context()))}
    assert "https://docs.example.test/private/x" not in ids
    assert not any("/private/" in u for u in seen)
    assert connector.stats["skipped_robots"] == 1

    connector, _ = make(pages, extra_config={"robots": "ignore"})
    ids = {d.external_id for d in await collect(connector.discover(context()))}
    assert "https://docs.example.test/private/x" in ids


@pytest.mark.asyncio
async def test_an_unreadable_robots_txt_means_do_not_crawl_that_host():
    connector, _ = make(robots=None)  # 404 = no restrictions
    assert len(await collect(connector.discover(context()))) > 0

    connector = WebConnector(
        {"seed_urls": ["https://docs.example.test/"]},
        http=client(lambda request: httpx.Response(403), raise_auth_errors=False),
        allow_private=True,
    )
    assert await collect(connector.discover(context())) == []
    assert connector.warnings


@pytest.mark.asyncio
async def test_canonical_urls_and_identical_content_are_deduplicated():
    pages = {
        "/": page("Home", ["/print/a", "/docs/a", "/copy"]),
        "/docs/a": page("A", canonical="https://docs.example.test/docs/a"),
        "/print/a": page("A", canonical="https://docs.example.test/docs/a"),
        "/copy": page("A"),  # same visible content as /docs/a but no canonical
    }
    connector, _ = make(pages)
    docs = await collect(connector.discover(context()))
    assert [d.external_id for d in docs].count("https://docs.example.test/docs/a") == 1
    assert connector.stats["skipped_duplicate"] >= 1


@pytest.mark.asyncio
async def test_sitemap_urls_are_discovered_and_kept_in_scope():
    sitemap = (
        '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://docs.example.test/docs/b</loc></url><url><loc>https://evil.test/x</loc></url></urlset>"
    )

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="Sitemap: https://docs.example.test/sitemap.xml")
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=sitemap)
        return httpx.Response(200, headers=HTML, text=page("Only " + request.url.path))

    connector = WebConnector(
        {"seed_urls": ["https://docs.example.test/docs/a"], "max_depth": 0, "request_interval_seconds": 0.1},
        http=client(handler, raise_auth_errors=False),
        allow_private=True,
    )
    ids = {d.external_id for d in await collect(connector.discover(context()))}
    assert ids == {"https://docs.example.test/docs/a", "https://docs.example.test/docs/b"}


@pytest.mark.asyncio
async def test_unchanged_pages_are_not_downloaded_again_conditional_get():
    async def lookup(url):
        return KnownDocument('"/docs/b"', "hash", {"etag": '"/docs/b"', "title": "B", "links": []})

    def handler(request):
        if request.url.path in ("/robots.txt", "/sitemap.xml"):
            return httpx.Response(404)
        assert request.headers.get("if-none-match") == '"/docs/b"'
        return httpx.Response(304)

    connector = WebConnector(
        {"seed_urls": ["https://docs.example.test/docs/b"], "max_depth": 0},
        http=client(handler, raise_auth_errors=False),
        allow_private=True,
    )
    docs = await collect(connector.discover(context(lookup=lookup)))
    assert len(docs) == 1 and docs[0].unchanged and docs[0].prefetched is None


@pytest.mark.asyncio
async def test_non_html_types_are_handled_or_skipped():
    def handler(request):
        p = request.url.path
        if p in ("/robots.txt", "/sitemap.xml"):
            return httpx.Response(404)
        if p == "/":
            return httpx.Response(200, headers=HTML, text=page("Home", ["/a.pdf", "/n.txt", "/img.png"]))
        if p == "/a.pdf":
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF-1.4")
        if p == "/n.txt":
            return httpx.Response(200, headers={"content-type": "text/plain"}, text="plain notes")
        return httpx.Response(200, headers={"content-type": "image/png"}, content=b"png")

    connector = WebConnector(
        {"seed_urls": ["https://docs.example.test/"], "max_depth": 1},
        http=client(handler, raise_auth_errors=False),
        allow_private=True,
    )
    docs = {d.external_id: d for d in await collect(connector.discover(context()))}
    assert docs["https://docs.example.test/a.pdf"].prefetched.file_name == "a.pdf"
    assert docs["https://docs.example.test/n.txt"].prefetched.text == "plain notes"
    assert "https://docs.example.test/img.png" not in docs
    assert connector.stats["skipped_type"] == 1


@pytest.mark.asyncio
async def test_a_failing_page_does_not_stop_the_crawl():
    def handler(request):
        p = request.url.path
        if p in ("/robots.txt", "/sitemap.xml"):
            return httpx.Response(404)
        if p == "/":
            return httpx.Response(200, headers=HTML, text=page("Home", ["/boom", "/ok"]))
        if p == "/boom":
            return httpx.Response(500)
        return httpx.Response(200, headers=HTML, text=page("OK"))

    connector = WebConnector(
        {"seed_urls": ["https://docs.example.test/"], "max_depth": 1},
        http=client(handler, max_retries=0, raise_auth_errors=False),
        allow_private=True,
    )
    ids = {d.external_id for d in await collect(connector.discover(context()))}
    assert "https://docs.example.test/ok" in ids and "https://docs.example.test/boom" not in ids
    assert connector.stats["errors"] >= 1


@pytest.mark.asyncio
async def test_cancellation_stops_discovery():
    connector, _ = make()

    async def cancelled():
        return True

    assert await collect(connector.discover(context(cancelled=cancelled))) == []


@pytest.mark.asyncio
async def test_config_validation():
    assert (await WebConnector({"seed_urls": ["https://docs.example.test/"]}).validate_config()).ok

    bad = await WebConnector({"seed_urls": ["ftp://x.test/"], "javascript_rendering": True, "max_depth": 99}).validate_config()
    joined = " ".join(bad.errors)
    assert not bad.ok and "http(s)" in joined and "JavaScript" in joined and "at most" in joined

    assert not (await WebConnector({}).validate_config()).ok


def test_urls_are_normalised():
    assert normalize_url("HTTPS://Docs.Example.test:443/a//b?utm_source=x&b=2&a=1#frag") == "https://docs.example.test/a/b?a=1&b=2"


@pytest.mark.asyncio
async def test_test_connection_reports_scope_and_robots_problems():
    connector, _ = make()
    assert (await connector.test_connection()).ok

    outside, _ = make(extra_config={"allowed_domains": ["other.test"]})
    assert not (await outside.test_connection()).ok

    blocked, _ = make(robots="User-agent: *\nDisallow: /")
    result = await blocked.test_connection()
    assert not result.ok and "robots" in result.message
