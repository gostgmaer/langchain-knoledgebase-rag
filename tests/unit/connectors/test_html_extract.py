from __future__ import annotations

from packages.connectors.html_extract import html_to_markdown

PAGE = """
<html lang="en"><head><title>Auth Guide | Example Docs</title>
<link rel="canonical" href="/docs/auth">
<meta name="description" content="How authentication works">
<script>trackEverything()</script><style>.x{}</style></head>
<body>
<nav><a href="/">Home</a><a href="/pricing">Pricing</a></nav>
<div class="cookie-banner">We use cookies. <button>Accept</button></div>
<div id="ad-slot" class="advert">BUY NOW</div>
<main>
<h1>Authentication Guide</h1>
<p>Tokens expire after <strong>15 minutes</strong>. See the <a href="/docs/refresh#top">refresh guide</a> and <a href="mailto:a@b.c">mail us</a>.</p>
<h2>Steps</h2>
<ol><li>Request a token</li><li>Call the API<ul><li>with a header</li></ul></li></ol>
<table><tr><th>Code</th><th>Meaning</th></tr><tr><td>401</td><td>Expired</td></tr></table>
<pre><code>curl -H "Authorization: Bearer $T" https://api</code></pre>
<figure><img src="x.png" alt="Flow"><figcaption>Token flow</figcaption></figure>
<p class="headline">Headline text is content, not an ad.</p>
</main>
<footer>Copyright junk</footer>
<script>more()</script>
</body></html>
"""


def test_boilerplate_is_removed_and_content_is_kept():
    md = html_to_markdown(PAGE, "https://docs.example.test/docs/auth").markdown

    for junk in ("Pricing", "cookies", "BUY NOW", "Copyright junk", "trackEverything", "more()"):
        assert junk not in md
    assert "Tokens expire after **15 minutes**" in md
    assert "## Steps" in md
    assert "Headline text is content" in md  # "headline" must not be mistaken for an ad


def test_structure_is_preserved():
    md = html_to_markdown(PAGE, "https://docs.example.test/docs/auth").markdown
    assert "1. Request a token" in md and "  - with a header" in md
    assert "| Code | Meaning |" in md and "| 401 | Expired |" in md
    assert "```" in md and "curl -H" in md
    assert "[Caption: Token flow]" in md


def test_links_are_absolute_and_fragments_and_mailto_dropped():
    page = html_to_markdown(PAGE, "https://docs.example.test/docs/auth")
    assert "[refresh guide](https://docs.example.test/docs/refresh)" in page.markdown
    assert page.links == ["https://docs.example.test/docs/refresh"]
    assert "mailto" not in page.markdown


def test_title_canonical_language_and_description():
    page = html_to_markdown(PAGE, "https://docs.example.test/docs/auth")
    assert page.title == "Auth Guide | Example Docs"
    assert page.canonical_url == "https://docs.example.test/docs/auth"
    assert page.language == "en"
    assert page.description == "How authentication works"


def test_a_page_with_no_main_element_still_yields_its_paragraphs():
    html = "<html><body><div><p>" + "Real content. " * 30 + "</p></div><div class='sidebar'>menu</div></body></html>"
    md = html_to_markdown(html, "https://x.test/").markdown
    assert "Real content." in md and "menu" not in md
