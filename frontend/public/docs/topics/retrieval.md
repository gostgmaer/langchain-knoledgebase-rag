Every retrieval, with its candidates, scores, and what actually reached the final answer — useful
for understanding *why* an answer cited what it did, or why it missed something you expected.
Queries themselves are stored only as a hash, never as plain text. To change how retrieval behaves
instead of just observing it, see [Retrieval Settings](/docs/retrieval-settings).

The list shows, per retrieval: when it ran, the query (as a hash prefix plus its character count),
the search strategy used (with a "rerank" badge when the cross-encoder ran), how many candidates
were considered, how many were used, and latency. Click a row to open **Why these chunks** below
it:

- Ids (retrieval, request, trace — each truncated), sub-query count, search/rerank latency, the
  top-k and minimum-relevance-score it ran with, and which reranker model was used.
- Every candidate chunk's scores (fused, vector, keyword, reranker — three decimal places, or
  "—" when a stage didn't run), its final rank (flagged "moved" if reranking changed its position),
  whether it was **used** or **dropped**, and which document, location (chunk index, page, section)
  and chunking strategy it came from. A document name links to its
  [detail page](/docs/documents); a version badge, source badge, or "superseded" badge appears
  when relevant.

Candidates are ranked by search score first; the reranker then re-scores them, and only the best
that clear the relevance floor become answer context.

![Retrieval log entry showing scored candidates](/docs/images/retrieval-log.png)
