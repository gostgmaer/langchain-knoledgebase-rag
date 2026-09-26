"""
HTML -> clean structured markdown.

Removes what is not content (scripts, styles, navigation, footers, cookie banners, ads, tracking, forms,
iframes) and keeps what is: title, headings, paragraphs, lists, tables, code blocks, links, and image
captions. Links are made absolute so citations and follow-up crawling work.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urldefrag, urljoin

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

_DROP_TAGS = {
    "script", "style", "noscript", "template", "svg", "canvas", "iframe", "object", "embed",
    "form", "input", "button", "select", "textarea", "nav", "footer", "aside", "dialog", "link", "meta",
}
# class/id fragments that mark boilerplate. Matched on whole tokens, not substrings, so "headline" or
# "addressing" are not mistaken for "ad".
_NOISE_TOKENS = {
    "cookie", "cookies", "consent", "gdpr", "banner", "advert", "advertisement", "ads", "adsbygoogle",
    "sponsor", "sponsored", "newsletter", "subscribe", "popup", "modal", "overlay", "share", "social",
    "breadcrumb", "breadcrumbs", "sidebar", "toc", "tracking", "promo", "related", "comments", "comment-form",
    "skip-link", "navbar", "menu", "footer", "header-nav",
}
_MAIN_SELECTORS = ("main", "article", "[role=main]", "#content", "#main", ".content", ".post", ".entry-content", ".markdown-body")
_BLOCK_TAGS = {"p", "div", "section", "article", "main", "header", "li", "ul", "ol", "table", "pre", "blockquote", "figure", "dl", "details", "summary"}


@dataclass
class ExtractedPage:
    title: str
    markdown: str
    links: list[str] = field(default_factory=list)
    canonical_url: str | None = None
    language: str | None = None
    description: str | None = None
    headings: list[str] = field(default_factory=list)


def _tokens(value: str | list[str] | None) -> set[str]:
    if not value:
        return set()
    text = " ".join(value) if isinstance(value, list) else value
    return {t for t in re.split(r"[\s_]+", text.lower()) if t}


def _is_noise(tag: Tag) -> bool:
    if tag.name in _DROP_TAGS:
        return True
    if tag.get("hidden") is not None or tag.get("aria-hidden") == "true":
        return True
    style = (tag.get("style") or "").replace(" ", "").lower()
    if "display:none" in style or "visibility:hidden" in style:
        return True
    if tag.get("role") in {"navigation", "banner", "contentinfo", "complementary", "dialog", "alert"}:
        return True
    tokens = _tokens(tag.get("class")) | _tokens(tag.get("id"))
    return bool(tokens & _NOISE_TOKENS)


def _clean(soup: BeautifulSoup) -> None:
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()
    for tag in list(soup.find_all(True)):
        if tag.decomposed if hasattr(tag, "decomposed") else False:
            continue
        if _is_noise(tag):
            tag.decompose()


def _pick_main(soup: BeautifulSoup) -> Tag:
    for selector in _MAIN_SELECTORS:
        found = soup.select_one(selector)
        if found is not None and len(found.get_text(strip=True)) > 200:
            return found
    body = soup.body or soup
    # Fallback: the block with the most paragraph text.
    best, best_len = body, 0
    for candidate in body.find_all(["div", "section", "article"]):
        length = sum(len(p.get_text(strip=True)) for p in candidate.find_all("p", recursive=False))
        if length > best_len:
            best, best_len = candidate, length
    return best if best_len > 200 else body


def _inline(node: Tag | NavigableString, base_url: str, links: list[str]) -> str:
    if isinstance(node, NavigableString):
        return re.sub(r"\s+", " ", str(node))
    name = node.name
    inner = "".join(_inline(c, base_url, links) for c in node.children)
    if name in ("strong", "b"):
        return f"**{inner.strip()}**" if inner.strip() else ""
    if name in ("em", "i"):
        return f"*{inner.strip()}*" if inner.strip() else ""
    if name == "code":
        return f"`{node.get_text()}`"
    if name == "br":
        return "\n"
    if name == "a":
        href = node.get("href")
        text = inner.strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            return inner
        absolute = urldefrag(urljoin(base_url, href))[0]
        links.append(absolute)
        return f"[{text}]({absolute})" if text else ""
    if name == "img":
        alt = (node.get("alt") or "").strip()
        return f"[Image: {alt}]" if alt else ""
    return inner


def _block(node: Tag, base_url: str, links: list[str], headings: list[str]) -> str:
    name = node.name
    if re.fullmatch(r"h[1-6]", name):
        text = _inline(node, base_url, links).strip()
        if not text:
            return ""
        headings.append(text)
        return f"\n{'#' * int(name[1])} {text}\n"
    if name == "p":
        text = _inline(node, base_url, links).strip()
        return f"\n{text}\n" if text else ""
    if name in ("ul", "ol"):
        return "\n" + _list(node, base_url, links, headings, ordered=name == "ol", depth=0) + "\n"
    if name == "pre":
        return f"\n```\n{node.get_text().strip(chr(10))}\n```\n"
    if name == "blockquote":
        inner = _children(node, base_url, links, headings).strip()
        return "\n" + "\n".join(f"> {line}" for line in inner.splitlines()) + "\n" if inner else ""
    if name == "table":
        return _table(node, base_url, links)
    if name == "figure":
        caption = node.find("figcaption")
        caption_text = caption.get_text(" ", strip=True) if caption is not None else ""
        if caption is not None:
            caption.extract()
        text = _children(node, base_url, links, headings).strip()
        if caption_text:
            text = f"{text}\n[Caption: {caption_text}]".strip()
        return f"\n{text}\n" if text else ""
    if name == "dl":
        out = []
        for child in node.children:
            if isinstance(child, Tag) and child.name in ("dt", "dd"):
                out.append(("**" + _inline(child, base_url, links).strip() + "**") if child.name == "dt" else _inline(child, base_url, links).strip())
        return "\n" + "\n".join(o for o in out if o) + "\n"
    if name == "hr":
        return "\n---\n"
    return _children(node, base_url, links, headings)


def _children(node: Tag, base_url: str, links: list[str], headings: list[str]) -> str:
    parts: list[str] = []
    buffer = ""
    for child in node.children:
        if isinstance(child, NavigableString):
            buffer += re.sub(r"\s+", " ", str(child))
        elif isinstance(child, Tag):
            if child.name in _BLOCK_TAGS or re.fullmatch(r"h[1-6]", child.name) or child.name in ("hr", "dl"):
                if buffer.strip():
                    parts.append(f"\n{buffer.strip()}\n")
                    buffer = ""
                parts.append(_block(child, base_url, links, headings))
            else:
                buffer += _inline(child, base_url, links)
    if buffer.strip():
        parts.append(f"\n{buffer.strip()}\n")
    return "".join(parts)


def _list(node: Tag, base_url: str, links: list[str], headings: list[str], *, ordered: bool, depth: int) -> str:
    lines: list[str] = []
    index = 0
    for li in node.find_all("li", recursive=False):
        index += 1
        marker = f"{index}." if ordered else "-"
        nested = [c for c in li.find_all(["ul", "ol"], recursive=False)]
        for n in nested:
            n.extract()
        text = _inline(li, base_url, links).strip()
        lines.append(f"{'  ' * depth}{marker} {text}")
        for n in nested:
            lines.append(_list(n, base_url, links, headings, ordered=n.name == "ol", depth=depth + 1))
    return "\n".join(lines)


def _table(node: Tag, base_url: str, links: list[str]) -> str:
    rows: list[list[str]] = []
    for tr in node.find_all("tr"):
        cells = [re.sub(r"\s+", " ", _inline(td, base_url, links)).strip().replace("|", "\\|") for td in tr.find_all(["th", "td"])]
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
    out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n" + "\n".join(out) + "\n"


def html_to_markdown(html: str, base_url: str = "") -> ExtractedPage:
    soup = BeautifulSoup(html, "lxml")

    canonical = None
    link = soup.find("link", rel=lambda v: v and "canonical" in (v if isinstance(v, list) else [v]))
    if link is not None and link.get("href"):
        canonical = urldefrag(urljoin(base_url, link["href"]))[0]
    description = None
    meta = soup.find("meta", attrs={"name": "description"})
    if meta is not None:
        description = (meta.get("content") or "").strip() or None
    language = (soup.html.get("lang") if soup.html else None) or None

    title = ""
    if soup.title is not None:
        title = soup.title.get_text(" ", strip=True)
    h1 = soup.find("h1")
    if not title and h1 is not None:
        title = h1.get_text(" ", strip=True)

    _clean(soup)
    main = _pick_main(soup)
    links: list[str] = []
    headings: list[str] = []
    body = _children(main, base_url, links, headings)
    body = re.sub(r"[ \t]+\n", "\n", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    if title and not body.startswith("# "):
        body = f"# {title}\n\n{body}" if body else f"# {title}"
    return ExtractedPage(
        title=title or (headings[0] if headings else ""),
        markdown=body,
        links=list(dict.fromkeys(links)),
        canonical_url=canonical,
        language=language,
        description=description,
        headings=headings,
    )
