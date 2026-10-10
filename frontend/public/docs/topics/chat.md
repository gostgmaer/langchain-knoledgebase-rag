Chat is where questions get answered. Type a question and Meridian retrieves the most relevant
passages from everything connected in [Knowledge Sources](/docs/knowledge-sources) and
[Documents](/docs/documents), then answers using only that retrieved context — not open-ended
knowledge, so answers stay grounded in your own content.

- **Citations.** Every answer lists the sources it actually used underneath the message: a
  document name, the connector it came from (Confluence, SharePoint, a web page, an upload...),
  a page number or section when one applies, and when it was last updated. Click a citation to
  open the original.
- **Feedback.** Use the thumbs up / thumbs down under an assistant's reply to rate it. This feeds
  [Analytics](/docs/operations) and the Feedback list, so a Tenant Admin can see which answers are
  landing and which aren't.
- **Formatting.** Assistant answers render Markdown — headings, lists, tables, code blocks, bold
  and italic text all show up formatted, not as raw symbols.

![Chat conversation with a cited answer](/docs/images/chat-conversation.png)

If an answer is missing a source you expected it to use, check that the right knowledge source has
actually finished syncing (see [Knowledge Sources](/docs/knowledge-sources)) and that your account
has access to it (see [Permissions and identity mappings](/docs/permissions)).
