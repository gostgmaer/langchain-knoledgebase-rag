The Dashboard is the first thing you see after signing in: a quick read on the health of your
workspace without opening every individual page. Think of it as a status check, not a place you
configure anything — every number on it links through to the page that actually explains it.

- **Stat cards** — Documents, Knowledge Bases, Agents, and Feedback totals, each a shortcut to its
  own page.
- **Usage, last 30 days** — total tokens, estimated cost, and the prompt/completion split. Full
  detail on [Usage](/docs/usage).
- **Retrieval health, last 7 days** — citation coverage, the empty-retrieval rate, average
  latency, and a combined "needs attention" count (documents that are stale or have never been
  retrieved). Full detail on [Observability](/docs/observability).
- **Knowledge sources** — how many are connected, how many need attention (errored or
  disconnected), documents added today, and failed documents. Full detail on
  [Knowledge Sources](/docs/knowledge-sources).
- **Recently uploaded documents** — the newest current, non-archived documents, with their
  chunking strategy and processing status, so you can confirm an upload landed.
- **Backend health** — whether the API service, its database, and Redis are each responding
  normally, shown with a colored status dot.

If any of these couldn't be loaded, a banner says so rather than silently showing stale or blank
numbers.

![Dashboard with health cards](/docs/images/dashboard-detail.png)
