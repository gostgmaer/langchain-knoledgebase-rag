Quick definitions for terms used throughout this guide.

- **[Knowledge Base](/docs/knowledge-bases)** — a named collection of documents that retrieval is
  scoped around; the boundary chat and search draw answers from.
- **[Knowledge Source](/docs/knowledge-sources)** — a connection to an external system (a website,
  Confluence, SharePoint/OneDrive, Teams, Slack) that Meridian keeps in sync automatically.
- **[Document](/docs/documents)** — a single file, either uploaded directly or discovered through
  a Knowledge Source, once it's been through the ingestion pipeline.
- **Chunk** — a document is split into chunks (smaller passages) before embedding, because
  retrieval and answers work on passages, not whole files. A document's chunking strategy and
  chunk count are both shown wherever it's listed.
- **Embedding** — a numeric representation of a chunk's meaning, used to find chunks that are
  semantically similar to a question even when they don't share its exact words.
- **Retrieval** — the step that finds which chunks are relevant to a question. See the
  [Retrieval Log](/docs/retrieval) for exactly what it found on any given query, and
  [Retrieval Settings](/docs/retrieval-settings) to tune how it behaves.
- **Reranking** — a second, slower scoring pass (a cross-encoder) that re-scores retrieval's
  candidates directly against the question, to push the genuinely best matches to the top.
- **[Agent](/docs/agents)** — a reusable assistant configuration: system prompt, model, and
  sampling parameters, used by Chat and the [embeddable widget](/docs/embeddable-widget).
- **[Model Profile](/docs/model-profiles)** — a configured LLM or embedding model connection that
  agents and retrieval run on. Shared platform-wide, not owned by one tenant.
- **[Prompt](/docs/prompts)** — a versioned template for an agent's system prompt. Every edit is a
  new version; nothing is overwritten.
- **[Tool](/docs/tools)** — something an agent can call mid-conversation: a built-in capability, or
  a custom webhook you define.
- **Tenant** — one organization/workspace on the platform. Most roles only ever see their own; see
  [Roles and permissions](/docs/roles-permissions).
- **[API Key](/docs/api-keys)** — credential for calling this platform's API outside a browser
  session, independent of anyone's login.

![Glossary](/docs/images/glossary.png)
