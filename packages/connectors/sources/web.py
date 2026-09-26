"""
Generic web page connector: a polite, bounded, policy-enforcing crawler.

Enforced on every request: domain allow-list, include/exclude URL patterns, robots.txt (Disallow and
Crawl-delay), depth and page limits, per-host throttling, timeouts, retries with backoff and a circuit
breaker (the shared ResilientHttpClient), redirect and SSRF checks. Duplicate URLs (canonical link,
tracking parameters, redirects) and duplicate content are collapsed. Conditional requests
(ETag / Last-Modified) avoid re-downloading unchanged pages.
"""

from __future__ import annotations

import fnmatch
import re
from collections import deque
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from lxml import etree

from packages.connectors.base import BaseKnowledgeConnector, ConfigField, ValidationResult
from packages.connectors.html_extract import html_to_markdown
from packages.connectors.http import ConnectorHttpError, ResilientHttpClient, assert_public_url
from packages.connectors.models import (
    ConnectionTestResult,
    DiscoveryContext,
    ExternalDocument,
    ExternalDocumentContent,
)

_TRACKING_PARAMS = {"gclid", "fbclid", "mc_cid", "mc_eid", "ref", "ref_src", "_ga", "yclid", "msclkid"}
_TEXT_TYPES = {"text/plain": ".txt", "text/markdown": ".md", "text/x-markdown": ".md"}
DEFAULT_USER_AGENT = "EasyDevRAGBot/1.0 (+knowledge-source crawler)"
MAX_LINKS_KEPT = 200


def normalize_url(url: str) -> str:
    """Lower-cased scheme/host, no fragment, no default port, no tracking parameters, stable query order."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    port = parts.port
    if port and not ((parts.scheme == "http" and port == 80) or (parts.scheme == "https" and port == 443)):
        host = f"{host}:{port}"
    query = urlencode(
        sorted(
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS
        )
    )
    path = re.sub(r"/{2,}", "/", parts.path) or "/"
    return urlunsplit((parts.scheme.lower(), host, path, query, ""))


def _pattern_target(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.netloc}{parts.path}"


class WebConnector(BaseKnowledgeConnector):
    type = "web"
    display_name = "Website"
    description = "Crawl public web pages within domains, URL patterns and limits you set."
    icon = "globe"
    credential_kind = "none"
    notes = (
        "Respects robots.txt and throttles requests. JavaScript-rendered content needs a headless browser, "
        "which this deployment does not include."
    )
    config_schema = (
        ConfigField("seed_urls", "Start URLs", "string_list", required=True, group="content",
                    help="Pages to start from, e.g. https://docs.example.com/", placeholder="https://docs.example.com/"),
        ConfigField("allowed_domains", "Allowed domains", "string_list", group="filters",
                    help="Only these hosts are crawled ('docs.example.com', or '*.example.com'). Defaults to the start URLs' hosts."),
        ConfigField("include_patterns", "Only URLs matching", "string_list", group="filters",
                    help="Patterns on host+path, e.g. docs.example.com/guide/*. Empty = everything on the allowed domains."),
        ConfigField("exclude_patterns", "Skip URLs matching", "string_list", group="filters",
                    help="e.g. docs.example.com/admin/*, docs.example.com/login/*"),
        ConfigField("max_depth", "Maximum crawl depth", "number", default=2, minimum=0, maximum=10, group="content",
                    help="0 = only the start URLs; 1 = plus pages they link to."),
        ConfigField("max_pages", "Maximum pages", "number", default=100, minimum=1, maximum=10000, group="content"),
        ConfigField("sitemap_url", "Sitemap URL", "url", group="content",
                    help="Optional. Also read from robots.txt or /sitemap.xml when 'Use sitemaps' is on."),
        ConfigField("use_sitemaps", "Use sitemaps", "boolean", default=True, group="content"),
        ConfigField("robots", "robots.txt", "select", default="respect", options=("respect", "ignore"), group="advanced",
                    help="Only choose 'ignore' for sites you own."),
        ConfigField("javascript_rendering", "Render JavaScript", "boolean", default=False, group="advanced",
                    help="Not available in this deployment."),
        ConfigField("request_interval_seconds", "Delay between requests (s)", "number", default=1.0, minimum=0.1,
                    maximum=60, group="advanced"),
        ConfigField("user_agent", "User agent", "string", default=DEFAULT_USER_AGENT, group="advanced"),
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._robots: dict[str, RobotFileParser | None] = {}
        self._robots_delay: dict[str, float] = {}
        self._robots_sitemaps: dict[str, list[str]] = {}
        self.stats: dict[str, int] = {"skipped_out_of_scope": 0, "skipped_robots": 0, "skipped_type": 0, "skipped_duplicate": 0, "errors": 0}
        self.warnings: list[str] = []

    # ------------------------------------------------------------------ setup

    def build_http(self) -> ResilientHttpClient:
        return ResilientHttpClient(
            headers={"User-Agent": self.configuration["user_agent"], "Accept": "text/html,application/xhtml+xml,text/plain,text/markdown,application/pdf;q=0.8,*/*;q=0.5"},
            min_interval=float(self.configuration["request_interval_seconds"]),
            max_concurrency=2,
            allow_private=self.allow_private,
            raise_auth_errors=False,
        )

    async def validate_settings(self) -> ValidationResult:
        result = await super().validate_settings()
        if self.configuration.get("javascript_rendering"):
            result.errors.append("JavaScript rendering is not available in this deployment.")
        for url in self.configuration.get("seed_urls") or []:
            parts = urlsplit(url)
            if parts.scheme not in ("http", "https") or not parts.netloc:
                result.errors.append(f"Start URL '{url}' must be an http(s) URL.")
        result.ok = not result.errors
        return result

    # ------------------------------------------------------------------ scope

    def _allowed_hosts(self) -> list[str]:
        configured = [d.strip().lower() for d in self.configuration.get("allowed_domains") or [] if d.strip()]
        if configured:
            return configured
        return sorted({(urlsplit(u).hostname or "").lower() for u in self.configuration.get("seed_urls") or []})

    def in_scope(self, url: str) -> bool:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if parts.scheme not in ("http", "https") or not host:
            return False
        if not any(fnmatch.fnmatchcase(host, pattern) for pattern in self._allowed_hosts()):
            return False
        target = _pattern_target(url)
        includes = self.configuration.get("include_patterns") or []
        if includes and not any(fnmatch.fnmatchcase(target, p) for p in includes):
            return False
        return not any(fnmatch.fnmatchcase(target, p) for p in self.configuration.get("exclude_patterns") or [])

    async def _robots_for(self, url: str) -> RobotFileParser | None:
        """The parsed robots.txt of the URL's host (None = no restrictions). Unreadable = disallow all."""
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin in self._robots:
            return self._robots[origin]
        parser: RobotFileParser | None
        try:
            response = await self.http.get(f"{origin}/robots.txt")
            if response.status_code in (404, 410):
                parser = None
            elif response.status_code >= 400:
                parser = RobotFileParser()
                parser.parse(["User-agent: *", "Disallow: /"])
                self.warnings.append(f"robots.txt at {parts.netloc} was not readable (HTTP {response.status_code}); skipping that host.")
            else:
                parser = RobotFileParser()
                lines = response.text.splitlines()
                parser.parse(lines)
                self._robots_sitemaps[origin] = [
                    ln.split(":", 1)[1].strip() for ln in lines if ln.lower().startswith("sitemap:")
                ]
        except ConnectorHttpError as exc:
            parser = RobotFileParser()
            parser.parse(["User-agent: *", "Disallow: /"])
            self.warnings.append(f"robots.txt at {parts.netloc} could not be fetched ({exc}); skipping that host.")
        self._robots[origin] = parser
        delay = parser.crawl_delay(self.configuration["user_agent"]) if parser else None
        if delay:
            self._robots_delay[origin] = float(delay)
            self.http.min_interval = max(self.http.min_interval, float(delay))
        return parser

    async def _allowed_by_robots(self, url: str) -> bool:
        if self.configuration.get("robots") == "ignore":
            return True
        parser = await self._robots_for(url)
        return parser is None or parser.can_fetch(self.configuration["user_agent"], url)

    # ------------------------------------------------------------------ sitemaps

    async def _sitemap_urls(self, limit: int) -> list[str]:
        if not self.configuration.get("use_sitemaps", True) and not self.configuration.get("sitemap_url"):
            return []
        candidates: list[str] = []
        if self.configuration.get("sitemap_url"):
            candidates.append(self.configuration["sitemap_url"])
        if self.configuration.get("use_sitemaps", True):
            for seed in self.configuration.get("seed_urls") or []:
                parts = urlsplit(seed)
                origin = f"{parts.scheme}://{parts.netloc}"
                await self._robots_for(seed)
                candidates += self._robots_sitemaps.get(origin, []) or [f"{origin}/sitemap.xml"]
        found: list[str] = []
        seen_maps: set[str] = set()
        queue = deque(dict.fromkeys(candidates))
        while queue and len(found) < limit and len(seen_maps) < 20:
            sitemap = queue.popleft()
            if sitemap in seen_maps:
                continue
            seen_maps.add(sitemap)
            try:
                response = await self.http.get(sitemap)
            except ConnectorHttpError:
                continue
            if response.status_code != 200:
                continue
            try:
                parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
                root = etree.fromstring(response.content, parser=parser)
            except etree.XMLSyntaxError:
                continue
            for loc in root.iter():
                if not isinstance(loc.tag, str) or not loc.tag.endswith("loc") or not (loc.text or "").strip():
                    continue
                target = loc.text.strip()
                if root.tag.endswith("sitemapindex"):
                    queue.append(target)
                else:
                    found.append(target)
        return found

    # ------------------------------------------------------------------ contract

    async def test_connection(self) -> ConnectionTestResult:
        seeds = self.configuration.get("seed_urls") or []
        if not seeds:
            return ConnectionTestResult(False, "No start URL configured.")
        seed = seeds[0]
        if not self.in_scope(seed):
            return ConnectionTestResult(False, f"The start URL {seed} is outside the allowed domains or patterns.")
        try:
            if not await self._allowed_by_robots(seed):
                return ConnectionTestResult(False, "robots.txt disallows crawling the start URL.", details={"robots": "disallowed"})
            response = await self.http.get(seed)
        except ConnectorHttpError as exc:
            return ConnectionTestResult(False, str(exc))
        ok = response.status_code < 400
        return ConnectionTestResult(
            ok,
            f"{seed} responded with HTTP {response.status_code}." if ok else f"{seed} responded with HTTP {response.status_code}.",
            details={"status": response.status_code, "content_type": response.headers.get("content-type"), "warnings": self.warnings},
        )

    async def discover(self, context: DiscoveryContext) -> AsyncIterator[ExternalDocument]:
        max_pages = int(self.configuration["max_pages"])
        max_depth = int(self.configuration["max_depth"])
        limit = min(max_pages, context.limit) if context.limit else max_pages

        queue: deque[tuple[str, int]] = deque()
        queued: set[str] = set()
        for seed in self.configuration.get("seed_urls") or []:
            url = normalize_url(seed)
            if url not in queued:
                queued.add(url)
                queue.append((url, 0))
        for url in await self._sitemap_urls(limit):
            url = normalize_url(url)
            if url not in queued and self.in_scope(url):
                queued.add(url)
                queue.append((url, 0))

        seen_ids: set[str] = set()
        seen_hashes: set[str] = set()
        yielded = 0

        while queue and yielded < limit:
            if context.cancelled is not None and await context.cancelled():
                return
            url, depth = queue.popleft()
            if not self.in_scope(url):
                self.stats["skipped_out_of_scope"] += 1
                continue
            try:
                if not await self._allowed_by_robots(url):
                    self.stats["skipped_robots"] += 1
                    continue
                document = await self._crawl_one(url, depth, context)
            except ConnectorHttpError as exc:
                self.stats["errors"] += 1
                self.warnings.append(f"{url}: {exc}")
                continue
            if document is None:
                continue
            if document.external_id in seen_ids:
                self.stats["skipped_duplicate"] += 1
                continue
            content_hash = document.prefetched.content_hash if document.prefetched else document.external_version or ""
            if content_hash and content_hash in seen_hashes:
                self.stats["skipped_duplicate"] += 1
                continue
            seen_ids.add(document.external_id)
            if content_hash:
                seen_hashes.add(content_hash)
            yielded += 1
            yield document

            if depth < max_depth:
                for link in document.metadata.get("links", []):
                    nxt = normalize_url(link)
                    if nxt in queued:
                        continue
                    queued.add(nxt)
                    if self.in_scope(nxt):
                        queue.append((nxt, depth + 1))
                    else:
                        self.stats["skipped_out_of_scope"] += 1

    async def _crawl_one(self, url: str, depth: int, context: DiscoveryContext) -> ExternalDocument | None:
        headers: dict[str, str] = {}
        known = await context.lookup(url) if context.lookup else None
        if known and known.metadata.get("etag"):
            headers["If-None-Match"] = known.metadata["etag"]
        if known and known.metadata.get("last_modified"):
            headers["If-Modified-Since"] = known.metadata["last_modified"]

        response = await self.http.get(url, headers=headers)
        if response.status_code == 304 and known is not None:
            return ExternalDocument(
                external_id=url,
                title=known.metadata.get("title") or url,
                canonical_url=url,
                external_version=known.external_version,
                unchanged=True,
                metadata={**known.metadata, "depth": depth},
            )
        if response.status_code >= 400:
            self.stats["errors"] += 1
            self.warnings.append(f"{url}: HTTP {response.status_code}")
            return None

        final_url = normalize_url(str(response.url))
        if final_url != url and not self.in_scope(final_url):
            self.stats["skipped_out_of_scope"] += 1
            return None
        content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
        etag = response.headers.get("etag")
        last_modified = response.headers.get("last-modified")
        updated_at = None
        if last_modified:
            try:
                updated_at = parsedate_to_datetime(last_modified).astimezone(UTC)
            except (TypeError, ValueError):
                updated_at = None

        metadata: dict[str, Any] = {
            "url": final_url,
            "domain": urlsplit(final_url).hostname,
            "depth": depth,
            "http_status": response.status_code,
            "content_type": content_type,
            "etag": etag,
            "last_modified": last_modified,
        }

        if content_type in ("text/html", "application/xhtml+xml", ""):
            page = html_to_markdown(response.text, final_url)
            if not page.markdown.strip():
                self.stats["skipped_type"] += 1
                return None
            canonical = normalize_url(page.canonical_url) if page.canonical_url else final_url
            external_id = canonical if self.in_scope(canonical) else final_url
            metadata.update(
                {
                    "title": page.title,
                    "language": page.language,
                    "description": page.description,
                    "headings": page.headings[:30],
                    "links": page.links[:MAX_LINKS_KEPT],
                    "canonical_url": external_id,
                }
            )
            content = ExternalDocumentContent(text=page.markdown, mime_type="text/markdown")
            title = page.title or external_id
        elif content_type in _TEXT_TYPES:
            external_id = final_url
            title = final_url.rsplit("/", 1)[-1] or final_url
            content = ExternalDocumentContent(text=response.text, mime_type=content_type)
        elif content_type == "application/pdf":
            external_id = final_url
            title = final_url.rsplit("/", 1)[-1] or final_url
            content = ExternalDocumentContent(data=response.content, file_name=title if title.lower().endswith(".pdf") else f"{title}.pdf", mime_type=content_type)
        else:
            self.stats["skipped_type"] += 1
            return None

        return ExternalDocument(
            external_id=external_id,
            title=title,
            canonical_url=external_id,
            external_version=etag or content.content_hash,
            updated_at=updated_at,
            mime_type=content.mime_type,
            metadata=metadata,
            prefetched=content,
        )

    async def fetch(self, document: ExternalDocument) -> ExternalDocumentContent:
        if document.prefetched is not None:
            return document.prefetched
        await assert_public_url(document.external_id, allow_private=self.allow_private)
        rediscovered = await self._crawl_one(document.external_id, int(document.metadata.get("depth", 0)), DiscoveryContext(source_id=None, tenant_id=None))  # type: ignore[arg-type]
        if rediscovered is None or rediscovered.prefetched is None:
            raise ConnectorHttpError(f"{document.external_id} could not be fetched.")
        return rediscovered.prefetched

    async def get_document(self, external_id: str) -> ExternalDocumentContent:
        return await self.fetch(ExternalDocument(external_id=external_id, title=external_id))

    def health_stats(self) -> dict[str, Any]:
        return {**super().health_stats(), "crawl": dict(self.stats), "warnings": self.warnings[:20]}
