Meridian doesn't cut formal numbered releases yet — there's no tag in the repository's history. The
versions below are groupings this guide assigns to the real commit history, newest first, so you can
see what actually changed and roughly when, even without a formal release process behind it.

## v0.5.0 — 2026-10-04 to 2026-10-10

- Admin-configurable [Platform Settings](/docs/platform-settings) — operational knobs moved out of
  environment variables, changeable without a redeploy.
- [API Keys](/docs/api-keys) for calling the platform's API outside a browser session.
- A public [embeddable chat widget](/docs/embeddable-widget) for external websites.
- A Slack [Knowledge Source](/docs/knowledge-sources) connector.
- Audit trail coverage extended to agents, model profiles, feature flags, API keys, prompts, and
  tools.
- Tenant names shown everywhere instead of raw tenant IDs.
- The in-app Documentation guide you're reading right now, later split into one page per topic.
- The CI/CD pipeline rebuilt: build, push, and deploy on every merge, moved to GHCR, limited to only
  the service(s) whose source actually changed, and tagged automatically on release.
- Fixes: a single default [Model Profile](/docs/model-profiles) is now enforced; the hybrid retriever
  no longer crashes on a knowledge base in a non-Latin script; a conversation-summary race and a
  connector sync-run race were both closed with real atomic database constraints; a Microsoft Graph
  webhook authentication bypass was closed; the Slack connector's channel allow/exclude lists now
  match a channel configured by id; the embeddable widget's public script is no longer blocked by the
  auth-gating proxy.

## v0.4.0 — 2026-09-30 to 2026-10-03

- Real product branding (Meridian) in place of a generic placeholder, across the UI.
- Fine-grained RBAC enabled — permission codes mapped and enforced, not just a feature-flag
  kill-switch. See [Roles and permissions](/docs/roles-permissions).
- Postgres row-level security wired into the production stack; scheduled database backups.
- Zero-downtime API deploys; production secrets moved to Docker secrets instead of plain `.env`.
- Real frontend test coverage (Vitest) and load-testing tooling (k6).
- [Prompts](/docs/prompts) gained real version history with rollback; a real [Tenants](/docs/tenants)
  directory; [Tools](/docs/tools) gained real, callable custom webhook tools.
- A responsive admin shell (collapsible sidebar, adaptive top bar), a real light/dark theme toggle,
  and a genuinely informative [Dashboard](/docs/dashboard).
- Fixes: a Model Profile's provider/model now actually control which LLM answers; pgvector confirmed
  as the real default vector backend, not Chroma.

## v0.3.0 — 2026-09-24 to 2026-09-26

- IAM enforcement wired into every API route, plus social sign-in account linking.
- The platform's first full QA pass — a dozen authorization and session-handling findings (open
  self-registration into the wrong workspace, members able to read admin-only data, a broken
  "browse as tenant" flow, dropped streaming errors, and more) found and fixed in the same pass.
- [Retrieval Log](/docs/retrieval) with per-chunk scores and an admin "explain" view; end-to-end
  [provenance](/docs/data-privacy), versioned retrieval visibility, and a longer audit trail.
- External [Knowledge Source](/docs/knowledge-sources) connectors: web, Wikipedia, Confluence,
  SharePoint/OneDrive, and Teams.
- Full environment and service-dependency documentation for the local stack, plus a preflight script
  that audits it.

## v0.2.0 — 2026-07-26 to 2026-08-08

- Embedding dimensions stabilized at 1536; a multi-turn chat message-duplication bug fixed.
- LangSmith observability wired into the application's startup lifecycle.
- Early knowledge-graph repositories and extraction logic.
- The UI's first brand color tokens and consistent component styling.

## v0.1.0 — 2026-07-18 to 2026-07-23

- The original architecture: dependency-injection containers, an agent runtime, an LLM provider
  abstraction, and a graph-based chat pipeline.
- Long-term and episodic memory, first implemented.
- Hybrid retrieval (BM25 plus cross-encoder reranking) with citations.
- Token streaming for chat responses.
- The first IAM integration — authentication middleware, bearer tokens, role-based access control.
- The document upload and ingestion API.

![Changelog](/docs/images/changelog.png)
