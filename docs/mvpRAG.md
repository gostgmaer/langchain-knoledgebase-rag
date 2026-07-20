> **Note on symbols**: ✅ = in scope for the named version (**not** "already built"), ⏸ = deferred/paused for a later version, ❌ = explicitly out of scope for now. This file is the **target roadmap** — what we've agreed to build and in which version. For what is *actually* built, working, broken, or missing right now, see [`docs/BUILD_STATUS.md`](./BUILD_STATUS.md), which is re-verified against the live code on every audit pass.

I agree. Given your goals and background, I think this is the right roadmap.

The only changes I'd make are very small, to make it even closer to what teams build in production.

⭐ Final MVP (v1.0)

## Phase 0 — Architecture & Planning
Groundwork that has to exist before any code is worth writing — otherwise later phases get rebuilt from scratch once the shape of the domain becomes clear.

- ✅ **Business Requirements** — who uses this, what problem it solves, what "done" looks like for a first release.
- ✅ **Use Cases** — concrete user flows (ask a question, upload a document, review a citation, escalate a dangerous action) that later phases must satisfy end to end.
- ✅ **Functional Requirements** — the feature list derived from the use cases (chat, RAG, tools, memory, HITL).
- ✅ **Non-Functional Requirements** — latency, cost, multi-tenancy, availability targets that shape architecture choices (e.g. async everywhere, connection pooling, caching).
- ✅ **Clean Architecture** — layering (`domain` → `infrastructure` → `api`/`agent`) so business logic doesn't depend on FastAPI, SQLAlchemy, or LangChain specifics.
- ✅ **Folder Structure** — the `packages/` layout (api, agent, conversation, graph, infrastructure, tools, rag, memory, config, domain, sdk, auth) that every later phase slots into.
- ✅ **Database Design** — the entity list in Phase 3, normalized and constrained (FKs, cascades, check constraints).
- ✅ **API Design** — resource-oriented REST surface: chat, conversations, documents, knowledge bases, search, models, prompts, tools, feedback.
- ✅ **Sequence Diagrams** — request → tenant/auth middleware → DI container → conversation manager → graph → tools/retrieval → response, for the main chat flow.
- ✅ **ER Diagram** — visualizing the Phase 3 schema and its relationships.
- ✅ **LangGraph Workflow Design** — the planner/router shape: retrieve → tool-call loop → llm → summarize → end.

## Phase 1 — Foundation
The scaffolding every other phase depends on: a server that starts, a config system that's typed, and enough observability to debug the phases built on top of it.

### Backend
- ✅ **FastAPI** — app factory + lifespan, not a single hardcoded route.
- ✅ **CLI** — a way to exercise the system without a frontend, for local development and smoke-testing.
- ✅ **Dependency Injection** — a container wiring config → infrastructure (DB, Redis, AI providers) → business services, so nothing hardcodes its own dependencies.
- ✅ **Configuration** — typed, env-backed settings per subsystem (app, api, db, redis, security, storage, queue, features, ai, iam, upload, notification), not scattered `os.getenv()` calls.
- ✅ **Logging** — structured (not `print`), with per-request correlation so a single request's log lines can be traced end to end.
- ✅ **Exception Handling** — one consistent error envelope across validation errors, HTTP errors, and unhandled exceptions — and crucially, internal details (tracebacks) must **not** leak to the client outside of a debug environment.
- ✅ **Health Checks** — an endpoint that actually verifies dependencies (DB, Redis, and ideally LLM provider reachability) are up, not just "the process is alive."
- ✅ **OpenAPI** — auto-generated docs (`/docs`, `/redoc`), gated behind environment/debug settings rather than always-on in production.

### DevOps
- ✅ **Docker** — a Dockerfile that builds a runnable image of the API.
- ✅ **Docker Compose** — local orchestration of the API + Postgres + Redis (+ vector store) for one-command local setup.
- ✅ **Environment Management** — `.env`/`.env.example` conventions, secrets never committed, and a documented list of required variables (in a real README).

## Phase 2 — IAM
Reuse EasyDev IAM rather than building auth from scratch — but the MVP still needs enough of a contract with that IAM system to actually gate access.

- ✅ **JWT Validation** — verify signature/expiry of tokens issued by EasyDev IAM before trusting any identity claim.
- ✅ **Refresh Token Validation** (if your IAM supports it) — so short-lived access tokens can be renewed without re-authenticating.
- ✅ **User Context** — resolve a verified user identity from the token, available to every downstream handler.
- ✅ **Tenant Context** — resolve which tenant a request belongs to, and reject requests that don't carry one.
- ✅ **Organization Context** — resolve organization membership where the IAM model supports multi-org tenants.
- ✅ **RBAC** — role-based checks (e.g. admin vs. member) gating sensitive actions.
- ✅ **Permission Validation** — fine-grained checks beyond role (e.g. "can this user delete this specific knowledge base").

**Important distinction this roadmap is deliberately explicit about:** tenant/org/user *context* (reading an ID and trusting it) is not the same as tenant/org/user *validation* (cryptographically proving the caller actually is who they claim). A real MVP needs both — trusting a header without verifying a signed token is not IAM, it's a placeholder for IAM.

## Phase 3 — Database
### Chat
- ✅ **Conversations** — one row per chat session, holding aggregate metadata (message/token/cost counts, start/end timestamps).
- ✅ **Messages** — one row per turn, linked to its conversation, with role, content, and optional citation/tool-call metadata.

### Knowledge Base
- ✅ **Knowledge Bases** — a named collection of documents scoped to a tenant, the unit users organize retrieval around.
- ✅ **Documents** — uploaded source files, their metadata (filename, size, mime type, owner), and processing status.
- ✅ **Document Versions** — re-uploads/edits of the same logical document, so retrieval can point at a specific version and old versions can be superseded without being destroyed.
- ✅ **Chunks** — the split units of a document actually indexed and retrieved, with offsets back to the source.
- ✅ **Embeddings Metadata** — which model/dimension/version produced each chunk's vector, so re-embedding after a model change is trackable.

### Jobs
- ✅ **Upload Jobs** — track the async pipeline (upload → parse → chunk → embed → index) so a client can poll progress instead of blocking on a slow upload.

### AI
- ✅ **AI Responses** — a record of what the model actually returned for a given turn, separate from the display-facing Message, useful for evaluation/audit.
- ✅ **Feedback** — thumbs up/down or structured ratings on responses, the seed data for future retrieval/prompt evaluation.

### Configuration
- ✅ **Prompt Templates** — versioned, named prompts rather than strings inlined in code.
- ✅ **Model Configurations** — named, versioned parameter sets (model, temperature, max tokens) so behavior changes are auditable and reproducible.

**Cross-cutting requirement, easy to skip:** every table above needs real foreign keys, `ondelete` rules, and check constraints — not just application-level "we'll remember to delete the children" logic. Migrations (Alembic) are how schema changes to this list get deployed safely; `create_all` is a dev-only shortcut, not a migration story.

## Phase 4 — LangChain
- ✅ **Chat Models** — a provider-agnostic wrapper so swapping Gemini/OpenAI/Anthropic/Groq doesn't touch call sites.
- ✅ **Embeddings** — same provider-agnostic wrapping for the embedding side of RAG.
- ✅ **Prompt Templates** — `ChatPromptTemplate`-style composition instead of f-strings, so prompts can be versioned and tested independently of code.
- ✅ **Output Parsers** — structured extraction (e.g. Pydantic-typed output) where a response needs to be machine-consumed, not just displayed.
- ✅ **Document Objects** — the `Document`/`Embeddings`/`VectorStore` LangChain abstractions used consistently through the RAG pipeline.
- ✅ **LCEL** — composing the above with `|` into runnable chains rather than imperative glue code, for consistency, streaming support, and tracing.

### Providers
- ✅ **Gemini**
- ✅ **OpenAI**
- ✅ **Anthropic**
- ✅ **Groq**

**Acceptance bar:** "providers wired" means each one can actually complete a real request with a real key, not just that the class instantiates without raising in a unit test.

## Phase 5 — LangGraph
- ✅ **GraphState** — the typed state object threading through every node: messages, retrieved documents, tool calls, user/conversation/thread IDs, running summary, metadata.
- ✅ **Nodes** — the actual units of work: retrieve, call the LLM, execute a tool, summarize.
- ✅ **Conditional Edges** — routing logic deciding which node runs next based on the current state (e.g. "the last AI message has tool_calls → go to the tool node").
- ✅ **Reducers** — how state updates merge across steps (e.g. `add_messages` appending rather than overwriting the message list).
- ✅ **Checkpointing** — persisting graph state between steps and turns, so a conversation can resume mid-graph.
- ✅ **Interrupt** — pausing graph execution at a specific node to wait for external input (the mechanism Phase 11's HITL depends on).
- ✅ **Resume** — continuing a previously interrupted run with the missing input supplied.
- ✅ **Streaming** — emitting partial output (tokens, intermediate node results) as the graph runs, rather than only returning a final blob.
- ✅ **Runtime Events** — structured events (node entered/exited, tool called, error raised) usable for logging, tracing, and future observability (LangSmith/OpenTelemetry, deferred to v1.1).

## Phase 6 — Session Management
- ✅ **Chat Sessions** — the logical grouping of a back-and-forth conversation, independent of any single HTTP request.
- ✅ **Thread IDs** — the identifier LangGraph's checkpointer uses to keep one conversation's state separate from another's.
- ✅ **Conversation History** — the ability to fetch prior turns for a conversation (for both context-building and for a client to render history) — note this needs an HTTP-reachable read path, not just DB-level storage.
- ✅ **Persistent Sessions** — checkpoints and history need to survive a process restart, which means a durable checkpointer backend (Postgres/Redis), not in-memory only.

## Phase 7 — Memory
### Short-term
- ✅ **Conversation Memory** — the running context (recent turns, summary) fed into each LLM call so it has continuity within a session.

### Long-term
- ✅ **Semantic Memory** — facts extracted from conversations, retrievable across sessions (e.g. "the user prefers concise answers").
- ✅ **Episodic Memory** — memory of specific past interactions/events, distinct from generalized facts.
- ✅ **User Preferences** — explicit or inferred settings that should persist and shape future responses.
- ✅ **User Facts** — durable facts about the user (role, domain, recurring context) available across every future conversation.

**Why long-term memory matters for an MVP, not just a nice-to-have:** without it, every new conversation starts from zero — the assistant can't build on anything it learned in a previous session, which is the difference between a chatbot and an assistant.

## Phase 8 — Document Processing
### Supported Documents
- ✅ **PDF**
- ✅ **DOCX**
- ✅ **Markdown**
- ✅ **HTML**
- ✅ **TXT**

### Processing
- ✅ **Parsing** — extracting raw text (and ideally structure — headings, tables) from each supported format.
- ✅ **Cleaning** — stripping boilerplate, fixing encoding issues, normalizing whitespace before chunking.
- ✅ **Metadata Extraction** — capturing source, page/section, author, and timestamps so citations can point somewhere specific.

### Chunking
- ✅ **Recursive** — general-purpose character/token-based splitting, the default strategy.
- ✅ **Markdown** — splitting along heading structure for Markdown sources, so chunks respect document sections.
- ✅ **Semantic** — splitting based on embedding-similarity boundaries rather than fixed size, for higher-quality retrieval on prose-heavy content.

### Embeddings
- ✅ **Multiple Providers** — the ability to embed with more than one backend (matching Phase 4's provider abstraction), so a tenant or deployment can choose.

### Indexing
- ✅ **Async** — indexing runs off the request path so uploads don't block on embedding generation.
- ✅ **Incremental** — re-indexing only what changed (a new document version) rather than the whole knowledge base.
- ✅ **Batch** — bulk-embedding many chunks efficiently rather than one API call per chunk.

## Phase 9 — Production Retrieval ⭐
This is the roadmap's centerpiece — the phase that turns "an LLM with some documents nearby" into an actual RAG system with defensible answers.

### Query
- ✅ **Query Classification** — deciding whether a query even needs retrieval, tool use, or a direct answer, before spending a retrieval call.
- ✅ **Query Rewriting** — reformulating a user's raw question into a better search query (e.g. resolving pronouns from conversation history).
- ✅ **Query Expansion** — generating related query variants to widen recall before ranking.
- ✅ **Query Embedding** — turning the (rewritten/expanded) query into the vector used for dense search.

### Search
- ✅ **Dense Retrieval** — vector similarity search against the embedded chunk index.
- ✅ **Similarity Search** — the core nearest-neighbor lookup against the configured vector store.
- ✅ **Hybrid Search** — combining dense (semantic) and sparse (keyword) retrieval, since neither alone is reliably best across query types.
- ✅ **BM25** — the sparse/keyword half of hybrid search, good at exact terms dense retrieval can miss (names, codes, acronyms).
- ✅ **Metadata Filtering** — narrowing retrieval by tenant, knowledge base, document, date, or other structured fields before/alongside similarity ranking.

### Ranking
- ✅ **Re-ranking** — a second, more expensive pass (often a cross-encoder) reordering the top candidates from the first-pass retrieval for higher precision.

### Prompt
- ✅ **Context Building** — assembling retrieved chunks into a prompt-ready context block, deduplicated and within a token budget.
- ✅ **Prompt Construction** — combining the context, conversation history, and the user's question into the final prompt sent to the LLM.
- ✅ **Citation Generation** — attaching source references (document, chunk, offset) to claims in the generated answer, so a user can verify where an answer came from.

**Why this phase is starred:** every other phase can be "good enough" for an MVP with a simpler implementation. This one can't — a RAG product whose answers can't be traced back to a source, or whose retrieval quality is unreliable, isn't a usable RAG product regardless of how polished everything around it is.

## Phase 10 — Tools
- ✅ **Knowledge Base Search** — a tool the agent can call explicitly to search a specific KB mid-conversation (distinct from the always-on retrieval in Phase 9).
- ✅ **Document Search** — searching within a single document rather than a whole knowledge base.
- ✅ **Web Search** — external search for questions the knowledge base can't answer.
- ✅ **Weather** — a concrete example external API integration, useful as a template for adding more tools.
- ✅ **News** — another external API integration example.
- ✅ **Calculator** — deterministic computation the LLM shouldn't be trusted to do via next-token prediction.

**Acceptance bar for "a tool exists":** it must be registered somewhere the agent can actually discover and invoke it, and the registration/execution call signature must actually match how the graph invokes tools — a tool file with real logic that's never wired into the registry doesn't count as done.

## Phase 11 — Human in the Loop
- ✅ **Interrupt** — pausing the graph before executing a sensitive action.
- ✅ **Resume** — continuing after a human approves (or denies) the paused action.
- ✅ **Approval Workflow** — the surface (API/UI) a human uses to review and decide on a paused action.

Examples:
- Delete KB
- Delete Documents
- Dangerous Operations

**Why this is in v1.0 and not deferred:** any system that can delete data or take irreversible external actions on a user's behalf needs a safety valve before it's trusted with real data — this isn't a "nice to have" polish item, it's a prerequisite for letting the agent have destructive tools at all.

## Phase 12 — Background Jobs
### Redis
- ✅ **Redis** — the broker/cache backing the queue and (optionally) checkpointing.

### Queue
- ✅ **BullMQ** *(or the Python-ecosystem equivalent — e.g. `arq`, Celery, or RQ; BullMQ itself is a Node.js library, so treat this line as "a real job queue," not literally BullMQ, in a Python codebase)*

### Jobs
- ✅ **Document Indexing** — the async worker side of Phase 8's indexing pipeline.
- ✅ **Embedding Generation** — batched embedding work running off the request path.
- ✅ **OCR** — text extraction from scanned/image-based PDFs, needed for a meaningful chunk of real-world "PDF" documents that aren't already text-layer PDFs.

## Phase 13 — Production
- ✅ **Redis Cache** — caching hot reads (e.g. frequently-asked-again queries, embeddings) to cut latency and cost.
- ✅ **Rate Limiting** — protecting the API and upstream LLM/embedding providers from abuse or runaway cost.
- ✅ **Retry Policies** — resilient handling of transient failures (provider timeouts, DB hiccups) instead of surfacing every blip as a hard error.
- ✅ **Health Monitoring** — Phase 1's health checks, extended to actually validate every critical dependency (DB, Redis, vector store, LLM providers).
- ✅ **Configuration Management** — Phase 1's typed settings, treated as a first-class production concern (safe defaults, no secrets in code, per-environment overrides).

## Phase 14 — APIs
- ✅ **Chat API** — the primary conversational surface: send a message, get a response, ideally with streaming and history endpoints alongside the core send-message route.
- ✅ **Conversation API** — create, list, fetch, and delete conversations — the resource Chat API messages belong to.
- ✅ **Upload API** — accept a document upload and kick off Phase 8/12's processing pipeline.
- ✅ **Search API** — expose Phase 9's retrieval directly, for clients that want raw search results rather than a chat-mediated answer.
- ✅ **Documents API** — manage uploaded documents (list, fetch metadata, delete, view processing status).
- ✅ **Knowledge Base API** — create/manage the KB containers documents belong to.
- ✅ **Feedback API** — submit and (for admins) review feedback on AI responses.

**Acceptance bar:** an API surface named here counts as done when its full resource lifecycle (at minimum create + read, ideally update/delete too) is registered and reachable — a router file that exists but isn't included in the app, or that only implements one verb of a multi-verb resource, is partial, not done.

## Phase 15 — Testing
- ✅ **Unit Tests** — isolated tests for individual functions/classes (parsers, chunkers, repositories) without external dependencies.
- ✅ **Integration Tests** — tests exercising real (or realistically faked) DB/Redis/vector-store interactions together.
- ✅ **LangGraph Workflow Tests** — tests asserting the graph routes and produces correct state transitions for representative inputs, not just that it "doesn't crash."
- ✅ **API Tests** — tests hitting the FastAPI routes via a test client, asserting status codes and response shapes.

**Acceptance bar:** these need real `assert` statements executed by a test runner (pytest) as part of a repeatable suite — a manual script that prints output for a human to eyeball is not a test suite, even if it exercises real code.

## Phase 16 — Deployment
- ✅ **Docker** — a working Dockerfile that builds and runs the app.
- ✅ **Docker Compose** — local/staging orchestration of the full stack.
- ✅ **Production Configuration** — environment-specific settings (secrets management, resource limits, logging verbosity) distinct from local dev defaults.

---

🚀 Version 1.1
### Retrieval
- ⏸ **Retrieval Evaluation** — systematic scoring of retrieval quality (precision/recall against a labeled set) so changes to chunking/ranking can be measured, not just vibes-checked.

### Tools
- ⏸ **Internal EasyDev API Integration** — tools that call other EasyDev-internal services, once those contracts are stable.

### Background Jobs
- ⏸ **Scheduled Re-indexing** — periodic refresh of embeddings/index without waiting for a manual re-upload.
- ⏸ **Cleanup Jobs** — garbage-collecting orphaned chunks, expired sessions, stale upload jobs.

### Observability
- ⏸ **LangSmith** — trace-level visibility into every LLM/tool call for debugging and prompt iteration.
- ⏸ **OpenTelemetry** — standard distributed tracing across the whole request path, not just the LLM calls.
- ⏸ **Token Usage** — per-request/per-tenant token accounting.
- ⏸ **Cost Tracking** — turning token usage into actual dollar-cost visibility, ideally per tenant/user.

### Production
- ⏸ **Circuit Breakers** — automatically failing fast (rather than piling up retries) against a provider that's clearly down.
- ⏸ **Feature Flags** — toggling in-progress features per environment/tenant without a redeploy.

### Frontend
- ⏸ **Admin Dashboard** — an internal UI for managing tenants, knowledge bases, and reviewing feedback/flagged content.
- ⏸ **Analytics** — usage dashboards (queries per day, top failing queries, feedback trends).

🚀 Version 2.0
### Advanced Retrieval
- ❌ **Parent Document Retriever** — retrieve small chunks for precision but return their parent document/section for full context.
- ❌ **Multi Vector Retriever** — index multiple representations per document (summary + full text + Q&A pairs) for different retrieval angles.
- ❌ **Self Query Retriever** — let the LLM translate natural language into structured metadata filters automatically.
- ❌ **Graph RAG** — retrieval over a knowledge graph instead of (or alongside) flat vector search.
- ❌ **Knowledge Graph** — the underlying structured entity/relationship store Graph RAG depends on.

### Advanced LangGraph
- ❌ **Subgraphs** — composing reusable graph fragments instead of one monolithic graph.
- ❌ **Parallel Execution** — running independent nodes concurrently instead of strictly sequentially.
- ❌ **Dynamic Routing** — routing decisions computed at runtime from more sophisticated policies than static conditional edges.
- ❌ **Durable Execution** — surviving process crashes mid-graph-run without losing in-flight work (beyond what checkpointing alone gives you).

### Multi-Agent
- ❌ **Supervisor** — an orchestrating agent delegating to specialized sub-agents.
- ❌ **Planner** — a sub-agent that breaks a complex request into an execution plan.
- ❌ **Researcher** — a sub-agent specialized in retrieval/investigation.
- ❌ **Writer** — a sub-agent specialized in producing the final response.
- ❌ **Reviewer** — a sub-agent that critiques/checks the Writer's output before it's returned.
- ❌ **Citation Validator** — a sub-agent (or deterministic check) verifying that generated citations actually support the claims they're attached to.

---

## Why I think this roadmap is a good fit

This roadmap follows a practical progression:

1. Build a solid platform (FastAPI, Docker, PostgreSQL, IAM).
2. Learn LLM orchestration (LangChain and LangGraph).
3. Implement production RAG (document ingestion, retrieval, citations).
4. Add memory and tool use so the assistant can maintain context and interact with external capabilities.
5. Finish with testing and deployment so the result is a deployable application rather than just a collection of experiments.

By deferring advanced retrieval techniques, graph-based approaches, and multi-agent systems to later versions, you keep the MVP focused while still creating a strong foundation that those future capabilities can build upon. Given your aim of creating an EasyDev product rather than a tutorial project, this is a balanced scope that emphasizes both learning and delivering something you can actually deploy.

---

## Where things actually stand

This roadmap describes the *target* — what's in scope and when. It intentionally says nothing about what's actually built yet. That's tracked separately and kept current in [`docs/BUILD_STATUS.md`](./BUILD_STATUS.md), which is re-verified against the running code (not just read from source) on every audit pass: what genuinely works end to end, what's a partial/unverified implementation, what's written but currently broken, and what hasn't been started.

As of the ninth audit pass, **chat works end-to-end for the first time** — a real, coherent Gemini response was returned twice in the same session, with genuine message persistence to a live database. The `GraphVisualizer` bug that caused three separate outages is fixed, and the weather tool works too. But this milestone sits on two still-broken bugs that simply haven't been triggered yet (a DB session shared across requests, and an LLM provider missing its API key, currently masked by an unrelated import-order accident) — so "chat works today" and "the underlying bugs are fixed" are deliberately tracked as separate claims in `BUILD_STATUS.md`. This pass reached 26.9% done, the highest of all nine passes. The biggest gaps between this roadmap and reality remain: Phase 2 (IAM — no real JWT/RBAC enforcement), Phase 9 (Production Retrieval — still the least-built phase relative to its own starred ambition; `packages/knowledge/` remains unreachable from any live request path despite real internal progress), and Phase 15 (Testing — still no real assertion-based test suite; this pass's two live-but-fragile bugs are exactly what integration tests exist to catch before "it works" becomes a false sense of security). See also [`docs/UNUSED_FILES.md`](./UNUSED_FILES.md) for a cleanup inventory of orphaned code and stray committed artifacts found along the way.
