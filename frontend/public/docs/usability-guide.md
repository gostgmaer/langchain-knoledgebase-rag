# Meridian usability guide

Meridian is a knowledge platform: connect your organization's content (websites, Confluence,
SharePoint, Teams, Slack, uploaded files), and ask questions about it in a chat that cites its
sources. This guide walks through every part of the product, organized by what you're trying to
do rather than by menu order.

Three kinds of accounts see different parts of this guide:

- **Customer** — asks questions in Chat, nothing else. The shortest path through this guide is
  [Chat](#chat).
- **Tenant Admin** — runs one workspace: connects knowledge, configures agents, manages the team.
  Most of this guide is written for you.
- **Admin** — runs the whole platform across every workspace (tenant): everything a Tenant Admin
  can do, plus platform-wide settings, feature flags, and the tenant directory.

Sections marked **Admin only** don't appear in a Tenant Admin's or Customer's menu at all — that's
expected, not a bug.

![Meridian dashboard overview](/docs/images/dashboard-overview.png)

---

## Table of contents

1. [Getting started](#getting-started)
2. [Chat](#chat)
3. [Dashboard](#dashboard)
4. [Knowledge Bases](#knowledge-bases)
5. [Knowledge Sources](#knowledge-sources)
6. [Permissions and identity mappings](#permissions-and-identity-mappings)
7. [Documents](#documents)
8. [Search](#search)
9. [Agents](#agents)
10. [Embeddable chat widget](#embeddable-chat-widget)
11. [Model Profiles](#model-profiles)
12. [Prompts](#prompts)
13. [Tools](#tools)
14. [Retrieval Log and Retrieval Settings](#retrieval-log-and-retrieval-settings)
15. [Analytics, Usage, Observability and Feedback](#analytics-usage-observability-and-feedback)
16. [Upload Jobs](#upload-jobs)
17. [Team](#team)
18. [API Keys](#api-keys)
19. [Settings](#settings)
20. [Tenants (Admin only)](#tenants-admin-only)
21. [Feature Flags (Admin only)](#feature-flags-admin-only)
22. [Platform Settings (Admin only)](#platform-settings-admin-only)
23. [Troubleshooting and FAQ](#troubleshooting-and-faq)

---

## Getting started

Sign in with your email and password, or with Google, Microsoft or Facebook if your administrator
has turned on social sign-in (see [Settings](#settings)). If someone invited you, follow the link
in your invitation email — it attaches you to the right workspace automatically.

Once signed in, the left sidebar is your menu, grouped by what each section is for: **Overview**
(Dashboard, Chat), **Knowledge** (Knowledge Bases, Knowledge Sources, Documents, Search), **Build**
(Agents, Model Profiles, Prompts, Tools), **Operations** (Analytics, Retrieval, Observability,
Usage, Feedback, Upload Jobs), and **Administration** (Team, API Keys, Settings, and, for Admins,
Tenants, Feature Flags and Platform Settings). A Customer account only ever sees Chat and Settings
— there's nothing missing, that's the whole menu for that role.

![Signed-in sidebar, showing the grouped menu](/docs/images/sidebar-overview.png)

---

## Chat

Chat is where questions get answered. Type a question and Meridian retrieves the most relevant
passages from everything connected in [Knowledge Sources](#knowledge-sources) and
[Documents](#documents), then answers using only that retrieved context — not open-ended
knowledge, so answers stay grounded in your own content.

- **Citations.** Every answer lists the sources it actually used underneath the message: a
  document name, the connector it came from (Confluence, SharePoint, a web page, an upload...),
  a page number or section when one applies, and when it was last updated. Click a citation to
  open the original.
- **Feedback.** Use the thumbs up / thumbs down under an assistant's reply to rate it. This feeds
  [Analytics](#analytics-usage-observability-and-feedback) and the [Feedback](#feedback) list, so a
  Tenant Admin can see which answers are landing and which aren't.
- **Formatting.** Assistant answers render Markdown — headings, lists, tables, code blocks, bold
  and italic text all show up formatted, not as raw symbols.

![Chat conversation with a cited answer](/docs/images/chat-conversation.png)

If an answer is missing a source you expected it to use, check that the right knowledge source
has actually finished syncing (see [Knowledge Sources](#knowledge-sources)) and that your account
has access to it (see [Permissions and identity mappings](#permissions-and-identity-mappings)).

---

## Dashboard

*Tenant Admin and Admin.* The Dashboard is the first thing you see after signing in: a quick read
on the health of your workspace without opening every individual page.

- **Retrieval health, last 7 days** — whether chat answers are consistently finding good matches.
- **Recently uploaded documents** — the newest additions, so you can confirm an upload landed.
- **Backend health** — whether the API and its dependencies are responding normally.

Think of it as a status check, not a place you configure anything — every number on it links
through to the page that actually explains it.

![Dashboard with health cards](/docs/images/dashboard-detail.png)

---

## Knowledge Bases

A Knowledge Base is a named collection of documents that retrieval is scoped around — the
boundary chat and search draw from. Most workspaces only need one ("Company Knowledge Base" or
similar), but splitting into more than one is useful when you want, say, engineering docs and HR
policies to never answer each other's questions.

To create one: **Knowledge Bases → New Knowledge Base**, give it a name, and save. Knowledge
Sources and uploaded Documents are then assigned to a Knowledge Base, either when you connect/
upload them or afterward.

![Knowledge Bases list](/docs/images/knowledge-bases-list.png)

---

## Knowledge Sources

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
  and manage its [permissions](#permissions-and-identity-mappings).

The source list's summary cards show, at a glance: total sources and how many are connected versus
paused; sources needing attention (errored or disconnected); total documents and chunks indexed,
with how many failed or are stale (behind the source's own latest content); and what changed
today (added / updated / removed).

![Knowledge source detail page with sync history](/docs/images/source-detail.png)

---

## Permissions and identity mappings

Some connectors (Confluence, SharePoint/OneDrive, Teams, private Slack channels) carry their own
access rules — who could see a page or file in the *original* system. Meridian can mirror those
rules so the same people (and only those people) can retrieve that content in chat here too.

On a source's detail page, the **Permissions** tab shows:

- **Default visibility** — who can see content from this source when it carries no specific
  access rule of its own: everyone in the tenant, or just administrators plus selected roles.
- **Identity mappings** — the link between an *external* identity (a Confluence/SharePoint user or
  group id, a Slack or Teams user id) and an *internal* one (a Meridian user, or a role). Add a
  mapping by entering the external id, choosing whether it's a **user** or a **group**, and
  choosing what it maps to internally. Getting the user/group choice right matters: a mapping
  saved as the wrong type silently never matches anything, so access never actually applies even
  though the mapping itself saved successfully.

![Permissions tab with identity mappings](/docs/images/permissions-tab.png)

If a source can't enumerate page-level permissions at all (some Confluence setups, for instance),
its content falls back to the source's own default visibility setting above.

---

## Documents

Documents are files uploaded directly, rather than discovered through a Knowledge Source. Drop a
file on **Documents** to upload it; Meridian loads it, cleans it, splits it into chunks, embeds
those chunks, and indexes them — the same pipeline a connector's content goes through, just
triggered by an upload instead of a sync.

A document's detail page shows its metadata, processing status, and version history (re-uploading
the same document creates a new version rather than silently overwriting the old one). Track an
upload still in progress on the [Upload Jobs](#upload-jobs) page.

![Documents list with upload in progress](/docs/images/documents-list.png)

---

## Search

Search runs the exact same hybrid retrieval and cross-encoder reranking that powers chat's
citations, but returns ranked passages directly instead of a composed chat answer — useful when
you want to see what retrieval finds for a query without an LLM's phrasing in the way. Filter by
document type, category, tags (all required to match), or which knowledge sources to search
within.

![Search results for a query](/docs/images/search-results.png)

---

## Agents

An Agent is a reusable assistant configuration: which system prompt it uses, which
[Model Profile](#model-profiles) it runs on, and its sampling parameters (temperature, and
similar). Rather than re-entering these every time, define an agent once — **Agents → New agent**
— and chat (or the embeddable widget, below) uses it directly.

![Agents list](/docs/images/agents-list.png)

---

## Embeddable chat widget

Any agent can be exposed as a small chat widget you embed on an external website — your marketing
site, a support portal, anywhere outside Meridian itself.

1. Open the agent, turn on **Embeddable chat widget**.
2. Add the exact origins (scheme + host + port, no path) allowed to use it — leaving this empty
   means no origin is allowed, so set it before you need the widget live.
3. Save. An **embed snippet** appears: a single `<script>` tag referencing this agent. Paste it
   into the target site's HTML.

If the widget is ever compromised or you just want a clean break, **Rotate widget id** invalidates
the current snippet immediately — update it wherever it's embedded afterward, or the old snippet
stops working.

![Agent widget settings with embed snippet](/docs/images/widget-embed.png)

---

## Model Profiles

*Tenant Admin and Admin.* A Model Profile is a configured LLM (and/or embedding model) connection
— provider, model name, and credentials — that agents and retrieval run on. Model Profiles are
shared platform-wide, not scoped to one workspace, and exactly one can be marked **default** at a
time (saving a new default automatically un-defaults the previous one).

![Model Profiles list](/docs/images/model-profiles-list.png)

---

## Prompts

Prompts are versioned templates for an agent's system prompt. Every edit creates a **new version**
instead of overwriting the last one, so nothing is ever silently lost — rolling back to an earlier
wording is just publishing that older version again. Add a short note on what changed when you
save a new version; it shows up in the version history later, when "why did this change" is
exactly what you'll want to know.

![Prompt version history](/docs/images/prompts-versions.png)

---

## Tools

Built-in tools (retrieval, and similar) power every chat automatically — nothing to configure.
A **Custom** tool definition with a URL becomes a real, callable webhook tool an agent can invoke
during a conversation; other tool categories currently exist as metadata only. Add one under
**Tools → New tool definition** with its webhook URL.

![Tools list, built-in and custom](/docs/images/tools-list.png)

---

## Retrieval Log and Retrieval Settings

**Retrieval Log** shows, for every chat turn, the candidate passages retrieval considered, their
relevance scores, and which ones actually reached the final answer — useful for understanding
*why* an answer cited what it did, or why it missed something you expected. Queries themselves are
stored only as a hash, never as plain text.

**Retrieval Settings** tunes how retrieval behaves for your workspace: how many results feed an
answer, and the minimum relevance score a passage needs to be considered. Leaving a field blank
keeps the platform-wide default (shown as its placeholder); changes apply within about 30 seconds,
no restart required.

![Retrieval log entry showing scored candidates](/docs/images/retrieval-log.png)

---

## Analytics, Usage, Observability and Feedback

*Tenant Admin and Admin.* Four related views on how the workspace is actually performing:

- **Analytics** — query volume per day, feedback trends over time, and the queries getting the
  most negative feedback (the ones most worth investigating first).
- **Usage** — token consumption and estimated cost, by day.
- **Observability** — retrieval health and indexed-document health signals (not answer accuracy),
  the most-retrieved documents, and an audit trail of who changed what configuration and when.
- **Feedback** — every thumbs up/down on an assistant response, filterable to just the negative
  ones, each linking back to the message it was left on.

![Analytics charts: queries per day and feedback trend](/docs/images/analytics-charts.png)

---

## Upload Jobs

Every document upload runs through a pipeline — queued, then running, then succeeded or failed —
and Upload Jobs shows that progress in real time. Paste a specific `upload_job_id` to jump
straight to one job, useful when a user reports a stuck or failed upload and gives you its id.

![Upload job progressing through its pipeline stages](/docs/images/upload-jobs.png)

---

## Team

Who's actually in this workspace, and anyone invited but not yet joined. **Invite a teammate**
sends an email with a join link; new recipients create an account (or sign in with Google,
Microsoft or Facebook using the same address), existing account holders just accept. Invitations
expire after 7 days — resend by inviting again if one lapses. Pending invitations can be revoked
before they're accepted.

![Team members and pending invitations](/docs/images/team-members.png)

---

## API Keys

For calling this platform's API from your own code — a script, a CI pipeline, a Zapier integration
— independent of a browser session. Create one under **API Keys → New API key**, name it something
that says what it's for ("CI pipeline", "Zapier integration"), and send it as
`Authorization: Bearer <key>` on requests. The key is shown once, at creation — copy it immediately,
it can't be retrieved again afterward (only revoked and replaced with a new one).

![API key created, shown once](/docs/images/api-key-created.png)

---

## Settings

Everyone's personal account settings, regardless of role:

- **Profile** — first/last/display name and phone number.
- **Password** — change the password you sign in with.
- **Connected accounts** — link or unlink Google, Microsoft or Facebook sign-in, where your
  administrator has turned them on. Signing in with a provider that confirms your email address
  connects it automatically the first time.

![Personal settings page](/docs/images/settings-profile.png)

---

## Tenants (Admin only)

The directory of every organization (tenant) on the platform. **Browse as** switches your session
into that tenant's workspace — handy for support and setup without needing a separate account in
every tenant. Recently-viewed tenants are listed as quick-access shortcuts above the full table.

![Tenant directory with browse-as shortcuts](/docs/images/tenants-directory.png)

---

## Feature Flags (Admin only)

Dynamic toggles for app behavior that take effect without a redeploy. Leave a flag's tenant field
blank to set the global default for everyone, or scope an override to one specific tenant.

![Feature flags list](/docs/images/feature-flags-list.png)

---

## Platform Settings (Admin only)

Operational knobs that apply platform-wide, not per workspace. A field left blank stays on its
built-in default (shown as that field's placeholder, so you can always see what "default" actually
means without guessing). Changes apply within about 30 seconds — no restart needed.

![Platform settings form](/docs/images/platform-settings.png)

---

## Troubleshooting and FAQ

**Chat didn't cite the document I expected.**
Confirm the knowledge source containing it has finished syncing (check its status on
[Knowledge Sources](#knowledge-sources) — "connected" with a recent "Last sync" time, not "error"
or "disconnected"), and that your account has access to it (see
[Permissions and identity mappings](#permissions-and-identity-mappings)). Also check
[Retrieval Settings](#retrieval-log-and-retrieval-settings) — a relevance threshold set too high
can exclude a genuinely relevant but lower-scoring passage.

**A knowledge source shows "error" or "disconnected."**
Open its detail page — the most recent sync run usually explains why (expired credentials, a
revoked permission, a source temporarily unreachable). Reconnecting usually means re-entering
credentials and letting the next sync run.

**I added an identity mapping but access still isn't working.**
Double-check the mapping's principal type — "user" vs. "group" — matches what you actually meant
to map. A mapping saved as the wrong type looks successful but silently never matches anything.

**The embeddable widget isn't loading on my site.**
Confirm the site's exact origin (scheme + host + port) is in the agent's allowed-origins list, and
that the widget is still enabled — rotating the widget id invalidates every snippet issued before
the rotation.

**My invitation link expired.**
Invitations expire 7 days after they're sent. Ask whoever invited you to send a new one from
[Team](#team).

**I can't see a page mentioned in this guide.**
Some pages are role-specific — see [Getting started](#getting-started) for what each role's menu
actually includes. If you believe you should have access to something you don't see, ask your
workspace administrator.
