Search runs the exact same hybrid retrieval and cross-encoder reranking that powers chat's
citations, but returns ranked passages directly instead of a composed chat answer — useful when
you want to see what retrieval finds for a query without an LLM's phrasing in the way.

Each result card shows the source document's name, the matching chunk's relevance score and its
position within the document, and the actual passage text that matched. Optional comma-separated
filters — document type, category, tags (every tag listed must match), and which knowledge
sources to search within — are applied inside the search itself, not as a filter over results
afterward, so they can surface a match that a looser query alone would have ranked too low to show.

![Search results for a query](/docs/images/search-results.png)
