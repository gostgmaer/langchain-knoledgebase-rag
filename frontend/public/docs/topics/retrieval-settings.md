Tunes how this workspace finds the text answers are built from. Changes apply within about 30
seconds — no restart required. Leaving a field blank keeps the platform-wide default (shown as its
placeholder); **Reset to defaults** clears every field back to that state in one click.

- **Chunks used per answer** (1–20) — how many passages feed an answer. More helps when an answer
  spans several passages; it also makes prompts longer and slower.
- **Minimum relevance score** (-10 to 10) — chunks the reranker scores below this are dropped; the
  single best chunk is always kept regardless. Higher is stricter: fewer but more relevant chunks.
  Only applies while reranking is on, and is disabled in the form when it's off.
- **Rerank with the cross-encoder** — a second, slower pass that re-scores candidates against the
  question. Off keeps the plain search ranking (faster; the minimum-relevance-score field above no
  longer applies). A "default" badge shows next to the toggle when it hasn't been overridden for
  this workspace.

Out-of-range values are flagged inline and block saving. The search strategy itself (shown as a
fixed value on this page) is platform-wide, not something this page controls.

To see the effect of a change, try a question in [Search](/docs/search) or Chat, then check the
[Retrieval Log](/docs/retrieval) for the real scores it produced.

![Retrieval settings form](/docs/images/retrieval-settings.png)
