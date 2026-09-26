"""
Wikipedia connector, on the official MediaWiki Action API (no scraping).

Controlled ingestion only: the administrator names articles (titles or URLs) and/or categories, with a
cap on how many articles are read. Every article is versioned by its revision id, so a changed article
becomes a new document version and an unchanged one is never downloaded or embedded again.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any
from urllib.parse import quote, unquote, urlsplit

from packages.connectors.base import BaseKnowledgeConnector, ConfigField, ValidationResult
from packages.connectors.http import ConnectorHttpError, ResilientHttpClient
from packages.connectors.models import (
    ConnectionTestResult,
    DiscoveryContext,
    ExternalDocument,
    ExternalDocumentContent,
)

USER_AGENT = "EasyDevRAGBot/1.0 (knowledge-source connector; contact: see deployment owner)"
_LANG = re.compile(r"^[a-z]{2,3}(-[a-z]+)?$")
_HEADING = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$")
BATCH = 20


def parse_article_url(url: str) -> tuple[str, str] | None:
    """'https://en.wikipedia.org/wiki/Alan_Turing' -> ('en', 'Alan Turing'); None if it is not a Wikipedia article URL."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    match = re.fullmatch(r"([a-z]{2,3}(?:-[a-z]+)?)\.wikipedia\.org", host)
    if not match or not parts.path.startswith("/wiki/"):
        return None
    return match.group(1), unquote(parts.path[len("/wiki/"):]).replace("_", " ")


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class WikipediaConnector(BaseKnowledgeConnector):
    type = "wikipedia"
    display_name = "Wikipedia"
    description = "Selected Wikipedia articles and categories, kept current by revision."
    icon = "book-open"
    credential_kind = "none"
    notes = "Uses the public MediaWiki API with a descriptive User-Agent. Content is CC BY-SA licensed: cite the article URL."
    config_schema = (
        ConfigField("language", "Language edition", "string", default="en", group="content", help="Wikipedia language code, e.g. en, de, fr."),
        ConfigField("titles", "Article titles", "string_list", group="content", placeholder="Alan Turing"),
        ConfigField("article_urls", "Article URLs", "string_list", group="content", placeholder="https://en.wikipedia.org/wiki/Alan_Turing"),
        ConfigField("categories", "Categories", "string_list", group="content", help="Articles directly in these categories, e.g. 'Computer scientists'."),
        ConfigField("max_articles", "Maximum articles", "number", default=50, minimum=1, maximum=500, group="filters",
                    help="Hard cap across titles, URLs and categories."),
    )

    def build_http(self) -> ResilientHttpClient:
        return ResilientHttpClient(
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            min_interval=1.0,
            max_concurrency=1,
            allow_private=self.allow_private,
        )

    async def validate_settings(self) -> ValidationResult:
        result = await super().validate_settings()
        language = str(self.configuration.get("language") or "en")
        if not _LANG.match(language):
            result.errors.append("Language must be a Wikipedia language code such as 'en'.")
        for url in self.configuration.get("article_urls") or []:
            if parse_article_url(url) is None:
                result.errors.append(f"'{url}' is not a Wikipedia article URL (expected https://xx.wikipedia.org/wiki/Title).")
        if not any(self.configuration.get(k) for k in ("titles", "article_urls", "categories")):
            result.errors.append("Add at least one article title, article URL or category.")
        result.ok = not result.errors
        return result

    # ------------------------------------------------------------------ API

    def _api(self, language: str) -> str:
        return f"https://{language}.wikipedia.org/w/api.php"

    async def _query(self, language: str, **params: Any) -> dict[str, Any]:
        response = await self.http.get(
            self._api(language),
            params={"action": "query", "format": "json", "formatversion": "2", "redirects": "1", **params},
            headers={"User-Agent": USER_AGENT},  # Wikimedia requires a descriptive agent on every request
        )
        if response.status_code != 200:
            raise ConnectorHttpError(f"Wikipedia API returned HTTP {response.status_code}.", status=response.status_code)
        data = response.json()
        if "error" in data:
            raise ConnectorHttpError(f"Wikipedia API error: {data['error'].get('info', 'unknown')}")
        return data

    async def test_connection(self) -> ConnectionTestResult:
        language = str(self.configuration.get("language") or "en")
        try:
            data = await self._query(language, meta="siteinfo", siprop="general")
        except ConnectorHttpError as exc:
            return ConnectionTestResult(False, str(exc))
        general = data.get("query", {}).get("general", {})
        return ConnectionTestResult(
            True, f"Connected to {general.get('sitename', 'Wikipedia')} ({language}).", authenticated=None,
            details={"generator": general.get("generator")},
        )

    def _wanted(self) -> list[tuple[str, str]]:
        """(language, title) pairs from titles and URLs, de-duplicated, in order."""
        language = str(self.configuration.get("language") or "en")
        wanted: list[tuple[str, str]] = [(language, t.strip()) for t in self.configuration.get("titles") or [] if t.strip()]
        for url in self.configuration.get("article_urls") or []:
            parsed = parse_article_url(url)
            if parsed:
                wanted.append(parsed)
        return list(dict.fromkeys(wanted))

    async def _category_titles(self, language: str, category: str, limit: int) -> list[str]:
        name = category if category.lower().startswith("category:") else f"Category:{category}"
        titles: list[str] = []
        cont: dict[str, str] = {}
        while len(titles) < limit:
            data = await self._query(language, list="categorymembers", cmtitle=name, cmtype="page", cmlimit=str(min(500, limit - len(titles))), **cont)
            titles += [m["title"] for m in data.get("query", {}).get("categorymembers", [])]
            cont = data.get("continue") or {}
            if not cont:
                break
        return titles[:limit]

    async def discover(self, context: DiscoveryContext) -> AsyncIterator[ExternalDocument]:
        cap = int(self.configuration["max_articles"])
        if context.limit:
            cap = min(cap, context.limit)
        language = str(self.configuration.get("language") or "en")

        wanted = self._wanted()
        for category in self.configuration.get("categories") or []:
            for title in await self._category_titles(language, category, cap):
                wanted.append((language, title))
        wanted = list(dict.fromkeys(wanted))[:cap]

        by_language: dict[str, list[str]] = {}
        for lang, title in wanted:
            by_language.setdefault(lang, []).append(title)

        seen: set[str] = set()
        for lang, titles in by_language.items():
            for start in range(0, len(titles), BATCH):
                if context.cancelled is not None and await context.cancelled():
                    return
                batch = titles[start : start + BATCH]
                data = await self._query(
                    lang, prop="info|revisions|categories", inprop="url", rvprop="ids|timestamp", cllimit="max", clshow="!hidden", titles="|".join(batch),
                )
                for page in data.get("query", {}).get("pages", []):
                    if page.get("missing") or page.get("invalid") or "pageid" not in page:
                        continue
                    revision = (page.get("revisions") or [{}])[0]
                    external_id = f"{lang}:{page['pageid']}"
                    if external_id in seen:
                        continue
                    seen.add(external_id)
                    canonical = page.get("canonicalurl") or f"https://{lang}.wikipedia.org/wiki/{quote(page['title'].replace(' ', '_'))}"
                    yield ExternalDocument(
                        external_id=external_id,
                        title=page["title"],
                        canonical_url=canonical,
                        external_version=str(revision.get("revid") or page.get("lastrevid")),
                        updated_at=_parse_time(revision.get("timestamp")),
                        mime_type="text/markdown",
                        metadata={
                            "article_title": page["title"],
                            "article_id": page["pageid"],
                            "revision_id": revision.get("revid") or page.get("lastrevid"),
                            "language": lang,
                            "canonical_url": canonical,
                            "revision_date": revision.get("timestamp"),
                            "categories": [c["title"].split(":", 1)[-1] for c in page.get("categories", [])][:50],
                            "license": "CC BY-SA 4.0",
                        },
                    )

    async def fetch(self, document: ExternalDocument) -> ExternalDocumentContent:
        lang, _, page_id = document.external_id.partition(":")
        data = await self._query(lang, prop="extracts", explaintext="1", exsectionformat="wiki", pageids=page_id)
        pages = data.get("query", {}).get("pages", [])
        extract = (pages[0].get("extract") if pages else "") or ""
        if not extract.strip():
            raise ConnectorHttpError(f"Article '{document.title}' has no readable text.")
        return ExternalDocumentContent(text=self._to_markdown(document.title, extract), mime_type="text/markdown")

    @staticmethod
    def _to_markdown(title: str, extract: str) -> str:
        out = [f"# {title}", ""]
        for line in extract.splitlines():
            match = _HEADING.match(line.strip())
            out.append(f"{'#' * len(match.group(1))} {match.group(2)}" if match else line)
        return "\n".join(out).strip() + "\n"

    async def get_document(self, external_id: str) -> ExternalDocumentContent:
        return await self.fetch(ExternalDocument(external_id=external_id, title=external_id))
