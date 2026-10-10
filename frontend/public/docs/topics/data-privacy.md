What actually gets stored, in plain terms.

- **Chat and Search queries are never stored as text.** Only a SHA-256 hash of the (normalized)
  query is kept, in the [Retrieval Log](/docs/retrieval) — enough to tell "this is the same
  question as before" without anyone, including an administrator, reading back what was asked.
- **Feedback comments are stored as the text you typed**, by design — a thumbs-down comment is
  explicit input meant to be read by whoever reviews it on [Feedback](/docs/feedback) or
  [Analytics](/docs/analytics). This is deliberately different from query storage above.
- **Source credentials are encrypted at rest.** An API token, app registration secret, or bot
  token entered when connecting a [Knowledge Source](/docs/knowledge-sources) is never shown back
  in plain text after saving.
- **Deleting a document removes it from the search index**, not just from the list — confirmed
  before you click it, since it can't be undone from this page. A document superseded by a newer
  version isn't deleted, just marked superseded; it stays out of search results but its history is
  kept.
- **Permissions mirror the source, not the other way around.** When a connector supports its own
  access rules (Confluence, SharePoint, Teams, private Slack channels), Meridian mirrors who could
  already see that content in the original system — see
  [Permissions and identity mappings](/docs/permissions). It doesn't grant access beyond what the
  source itself allowed.
- **Configuration changes are audited**, not content. [Observability](/docs/observability)'s audit
  trail records who changed what setting and when — not what anyone asked in chat.
- **An API key is shown exactly once**, at creation. After that, only a short prefix is ever shown
  again — enough to recognize which key is which, not enough to use it. See
  [API Keys](/docs/api-keys).

![Data handling overview](/docs/images/data-privacy.png)
