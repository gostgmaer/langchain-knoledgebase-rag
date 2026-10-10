How retrieval is performing and how healthy the indexed documents are. These are health
signals — whether retrieval is finding *something*, and whether what it indexed is current — not a
judgment of answer accuracy. Switch the range (**7/30/90 days**) at the top; the **Retrieval log**
button jumps to the [per-query detail](/docs/retrieval) behind any of these numbers.

**Retrieval health, for the selected range:**
- **Retrievals** — how many retrieval calls ran.
- **Avg / p95 latency** — typical and worst-case time to retrieve.
- **Candidates → kept** — average candidates considered vs. how many actually made it into an
  answer.
- **Citation coverage** — the share of answers that cite at least one source, and the raw count
  behind it (e.g. "42 of 50 answers cite a source").
- **Empty retrievals** — the share where nothing was found at all.
- **Low-confidence** — the share where even the best reranker score came back below zero.

**Document health, right now (not range-limited):**
- **Stale embeddings** — documents indexed under an older embedding pipeline version than the one
  currently in use. A **Re-index outdated** button appears next to the document-status badges to
  queue them for re-embedding in one click (disabled when there are none).
- **Never retrieved** — documents that finished processing successfully but no answer has ever
  pulled from.
- Document counts by status (e.g. `READY`, `FAILED`) as badges next to the re-index button.

**Most retrieved documents** lists the documents retrieval leans on most: how many times each was
considered, how many times it actually made it into an answer, and its average reranker score —
each name links to that [document's detail page](/docs/documents).

**Audit trail** is a searchable, paginated log of who changed what configuration and when —
filterable by action (e.g. `agent.updated`). A system-triggered event (like an automatic sync or
re-index) shows "system" instead of a user, rather than an unresolved blank.

![Observability health cards and audit trail](/docs/images/observability-summary.png)
