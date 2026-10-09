A Knowledge Source is a connection to an external system that Meridian keeps in sync automatically
— discovering new and changed content, converting it, chunking it, embedding it, and indexing it,
without anyone manually re-uploading anything. Today's connectors:

| Connector | What it reads |
|---|---|
| **Website** | Public web pages, crawled within the domains and URL patterns you set, respecting `robots.txt`. |
| **Wikipedia** | Specific articles or categories you name, kept current by revision. |
| **Confluence** | Pages (and optionally attachments) from selected spaces, with page-level restrictions honored. |
| **SharePoint / OneDrive** | Document libraries, kept in sync with Microsoft Graph's change tracking and item-level permissions. |
| **Microsoft Teams** | Channel conversations, one document per thread, with channel-membership access. |
| **Slack** | Channel conversations, one document per thread, with channel-membership access for private channels. |

### Adding a source

**Knowledge Sources → Add source**, pick a connector type, and fill in its settings — the form is
generated from that connector's own schema, so required fields, help text and placeholders are
specific to what you picked (a Confluence source asks for a base URL and spaces; a Website source
asks for start URLs and crawl depth; and so on). Most connectors that read a system with its own
login (Confluence, SharePoint, Teams, Slack) need credentials — an API token, app registration, or
bot token, depending on the connector — entered once and stored encrypted.

![Add a knowledge source form](/docs/images/add-source-form.png)

### Keeping it in sync

Each source runs on a **schedule** (pick an interval) or is triggered by a **webhook** from the
source system itself, where supported. From the source list or its own detail page you can also:

- **Sync now** (or **Crawl now** for a Website source) — trigger an out-of-schedule run.
- **Pause** / **Resume** — temporarily stop discovering new content without disconnecting it.
- **Configure** — open the source's detail page to change its settings, review recent sync runs,
  and manage its [permissions](/docs/permissions).

The source list's summary cards show, at a glance: total sources and how many are connected versus
paused; sources needing attention (errored or disconnected); total documents and chunks indexed,
with how many failed or are stale (behind the source's own latest content); and what changed
today (added / updated / removed).

![Knowledge source detail page with sync history](/docs/images/source-detail.png)
