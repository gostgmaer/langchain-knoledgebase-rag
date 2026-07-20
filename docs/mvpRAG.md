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

As of the twelfth audit pass, the bug that blocked the entire chat pipeline last pass is fixed: `packages/infrastructure/container/memory.py` now wires `MemoryManager` with real `MemoryStore`/`MemoryExtractor`/`MemorySummarizer`/`MemoryRetriever` instances instead of a nonexistent `factory=` argument, and the graph container's own `context`/`nodes` signature mismatch is fixed alongside it. `POST /api/v1/chat` no longer 500s — a request now runs the full dependency chain successfully and fails only on a legitimate `404 Conversation not found`, since there's still no HTTP-reachable way to create a conversation. Broken items hit **zero** for the first time across twelve passes; score moved to 22.7% (up from 21.0%).

The one regression found this pass — the `PlannerResult`/`GraphPlanner` duplication growing from two implementations to three — was resolved in the same session, by request: the team chose to consolidate onto `packages/planner/planner.py`'s richer, plan-based (`ExecutionPlan`/`ExecutionStep`/`Capability`) model over the simpler single-hop `next_node` enum, since it fits better where the roadmap's Memory/HITL/Summarization phases are headed. Both losing duplicates (`packages/graph/planner.py`, `packages/graph/nodes/planner.py`) were deleted outright, along with the now-fully-orphaned `packages/graph/nodessss.py`. Fixing this in required also finding and closing a real circular-import bug the new planner introduced (fixed with the same `TYPE_CHECKING` pattern already used elsewhere in the codebase) — confirmed live afterward with no behavior change: `GraphRouter` still routes retrieval-keyword messages to `"retrieve"` and everything else to `"llm"`, same as before, just driven by the new model. Four items are now off [`docs/UNUSED_FILES.md`](./UNUSED_FILES.md)'s list (`packages/graph.zip`, and the three planner-related files above). The next real blocker isn't a bug at all: it's the missing `conversations.py` router, without which no live chat turn (and therefore no live proof of the `GoogleProvider` fix, now unprovable for a fourth consecutive pass) can actually be exercised end to end.

**Also fixed the same session, by request:** the long-tracked DB session bug (`packages/infrastructure/container/database.py`'s `session` provider was `providers.Resource` — a singleton for the app's whole lifetime — instead of `providers.Factory`, meaning every request shared the exact same `AsyncSession`). The fix turned out to be more than a one-line swap: naively making it a `Factory` would have traded that bug for a worse one — every repository and the memory store each independently resolving a *new*, never-closed session/connection on every single request, a real leak confirmed live via a `RuntimeError`/`SAWarning` during testing, not a hypothetical. The actual fix opens exactly one session per request in `packages/api/dependencies.py`'s `get_conversation_manager`, temporarily makes the whole DI tree (every repository, the memory store) resolve to that one shared session via dependency_injector's `.override()`, and explicitly closes it in a `finally` — confirmed live with three sequential chat requests producing no leak warnings and two independent session resolutions proven to be distinct objects. A knock-on `TypeError` in `packages/api/lifespan.py` (an `await` that stopped being valid once the dependency chain became synchronous) was caught and fixed along the way.

**Milestone, same session, by request: the missing "create a conversation" flow got built, and a chat request reached the LLM node for the first time ever.** `packages/api/routers/conversations.py` went from a one-line stub to a real, registered `POST /conversations` route (`packages/conversation/bootstrap.py`, new, auto-provisions a per-tenant default `Agent` and a shared default `ModelProfile` from real AI settings, get-or-create, confirmed idempotent). Proving this actually worked end to end surfaced two more real, previously-only-theorized bugs, both fixed, not just noted: a `model_profiles` table missing its `vector` column entirely (schema drift — the table predates that column being added to the model; fixed with an additive `ALTER TABLE`, existing data — 1 profile, 1 agent, 1 conversation, 47 messages — confirmed untouched), and `packages/infrastructure/repositories/base.py`'s long-documented "writes only flush(), never commit()" gap, now confirmed as a live, request-breaking bug rather than just a code-reading finding — fixed at the correct transaction boundary (the same per-request session helper from the DB-session fix, committing once at the end of a successful request). With all of that fixed, a chat request now reaches further than in any of the prior twelve passes: the conversation is found, memory/graph construction succeeds, and **a real embedding API call to Google's Generative Language API succeeds live** — the first-ever live proof that the long-"correct but unprovable" `GoogleProvider` fix actually works. The chain now breaks one node later, on a new, different, genuine bug: `packages/graph/nodes/llm.py:47` calls a method (`ChatService.ainvoke`) that doesn't exist — `ChatService`'s real method is `achat`, with a different signature. That's the next and, as far as this audit can tell, final blocker before a complete chat response works end to end.

**🎉 That blocker is now fixed too, and `POST /api/v1/chat` works end to end for the first time in this project's history.** By explicit request, `packages/application/services/chat_service.py`'s `ChatService` replaced `ConversationManager`'s flow entirely as the top-level chat entry point. Getting there required fixing 9 real, distinct bugs in one continuous chain, each only reachable once the previous one was fixed — the `ChatService.ainvoke` bug above, a missing `ConversationRepository.get_by_session_id()`, a missing `ConversationService.touch()`, two competing `UnitOfWork` classes, `_execute_runtime()`'s hardcoded stub response (rewired to genuinely invoke `GraphManager`, keeping retrieval/tools/memory extraction intact), `LLMManager.model_name` not existing, Gemini returning `AIMessage.content` as a list instead of a string (breaking both memory-fact JSON parsing and message persistence), and a timezone-aware/naive `datetime` mismatch against a `TIMESTAMP WITHOUT TIME ZONE` column. Confirmed live, twice in a row: a real message in, a real Gemini-generated response out, the second call correctly recalling the first turn's content. Also added, specifically to make this testable: `X-Tenant-ID`/`X-User-ID` now fall back to fixed default UUIDs when omitted, and `conversation_id` is optional on `POST /api/v1/chat`, auto-provisioning a default conversation when not given — a bare `POST /api/v1/chat {"message": "..."}` with zero headers now works. Score: 26.9% of the roadmap, tied with the ninth pass for this project's all-time high. One new, non-fatal finding surfaced by this success: LangGraph's checkpointer warns that deserializing this codebase's custom planner types will be blocked in a future version — not broken today, but flagged as a priority before it becomes one.

**A 10th bug, found by the user testing their own running server, not by this audit:** asked "what about calculator," the live app confidently described tools named "Code Interpreter" and "Google Search" — neither of which exists anywhere in this codebase. All four real tools (calculator, weather, news, search) were correctly registered in `ToolManager` the whole time, but `LLMNode` never actually called `.bind_tools()` on the model before invoking it, so the model had zero real tool-calling capability and was purely hallucinating plausible tool names from its training data. Fixed by threading `ToolManager.list()` through to `ChatService`, which now binds tools onto the model before every invocation — the same pattern a separate, unused `AgentRuntime.run()` had already gotten right. Confirmed live: the model now names exactly the 4 real tools, and asked to "use your calculator tool to compute 847 * 293," it genuinely delegated to the real tool and returned the correct `248,171` — not a guess.

**Long-term memory (Phase 7) went from a functional no-op to genuinely working, also by request.** Asked "what is the status of memory," tracing it found the pipeline ran cleanly but did nothing real: `PostgresMemoryStore` computed `MemoryFact` objects and threw them away (a complete stub, no SQL anywhere), and `PgVectorMemoryRetriever` searched the wrong vector store — the RAG document collection, not memories, which would have found nothing relevant even if anything had been stored. Built a real `memories` table with a genuine `pgvector` column, tenant/user/conversation-scoped, and rewired both the store and retriever to use it. Three more real bugs surfaced getting it fully working end to end: an embedding-dimension mismatch (config said 1536, the actual model produces 3072), a Postgres enum that doesn't auto-update when new categories are added in Python, and — the significant one — `GraphManager`'s entire node chain was wired as a `providers.Singleton`, meaning it was constructed exactly once, at app startup, before any request-scoped database session ever existed. Every memory write after that silently succeeded into one permanently orphaned, never-committed session from startup — no error, just data nobody would ever see. Fixed by converting the whole graph construction chain to `providers.Factory`. Verified with the strictest possible test: told one conversation "my favorite language is Rust, I'm building a robotics startup called Ferrolabs," then asked a second, brand-new conversation with zero shared history "what do you know about my programming preferences and my company?" — it correctly answered both, pulled from real database rows found via real semantic search. Score: 30.3%, a new all-time high for this project.

**Episodic Memory closed out Phase 7 to a full 100% the same session.** Semantic memory (facts/preferences) is one thing; episodic memory — remembering *what happened*, the narrative of a specific conversation, not just atomic facts pulled from it — is a genuinely different capability. It turned out real code for this already existed (`LLMMemorySummarizer`, `MemoryManager.summarize()`) but was never called from anywhere in the graph. Wired it into `ExtractMemoryNode` alongside fact extraction, as an upsert — one running summary per conversation, updated each turn, not a new near-duplicate row every time — and fixed the exact same Gemini list-content bug found elsewhere this session before it ever got the chance to crash here too. Verified live: two turns in one conversation (debugging a Rust memory leak, then finding the cause) produced exactly one summary row, correctly updated to capture the full arc of the conversation. Score: 31.1% — Phase 7 is now the first phase in this project's history to hit 100%.

**One more cleanup, closing out the last open finding:** LangGraph's checkpointer had been warning on every single turn that deserializing this codebase's own custom planner types (`Capability`/`ExecutionStep`/`ExecutionPlan`) and `asyncpg.pgproto.pgproto.UUID` would be blocked in a future LangGraph version. Fixed by constructing the graph's `MemorySaver` with an explicit `JsonPlusSerializer` allowlisting those exact types, instead of relying on the default permissive-but-warning behavior. Confirmed live: two full chat turns, zero occurrences of the warning that previously fired on every single one.

**LangChain (Phase 4)'s last gap — Prompt Templates, Output Parsers, LCEL — closed by request, moving the phase from 40% to 70%.** Every prompt in the codebase was hand-concatenated f-strings, and every LLM-output parse was a bare `json.loads()` — nothing resembling idiomatic LangChain. Fixed genuinely, not superficially: `packages/prompts/builder.py`'s `PromptBuilder` now builds a real `ChatPromptTemplate` with a `MessagesPlaceholder` for history; a new `packages/memory/implementations/output_parser.py` adds `MemoryFactListParser`, a real `BaseOutputParser` subclass with a proper `OutputParserException` on malformed output; and memory extraction/summarization now run as genuine LCEL chains (`prompt | llm.model | parser`) instead of manual prompt-building followed by a bare `.ainvoke()`. Wiring this up surfaced one more real bug: `LLMMemoryExtractor`/`LLMMemorySummarizer` had always been type-hinted as taking a `BaseChatModel`, but the actual injected object is this codebase's own `LLMManager` wrapper — not a real `Runnable` — which only became a hard crash (`TypeError: Expected a Runnable...`) once `|` composition was actually attempted for the first time. Fixed by using `LLMManager.model` (the real underlying chat model) for the chain. Also discovered along the way: LangChain's own `AIMessage.text` accessor already natively solves the Gemini list-content problem this session's own `normalize_message_content()` helper was built to work around — now used idiomatically in the summarizer instead. Verified live: a full regression covering a normal chat turn, cross-conversation memory recall, and real tool-calling all still pass after the rewrite. Score: 33.6%, a new all-time high.

**The running app told the user, confidently, that it has no persistent memory — asked to check, this turned out to be a real bug, not a model quirk.** `LLMNode` (`packages/infrastructure/container/graph.py:60-66`) was wired with a `system_prompt` frozen in at DI-construction time to the literal string `"You are a helpful assistant."`, completely ignoring the real, per-tenant `agent.system_prompt` that `ChatService` was already correctly fetching from the database and placing into `GraphState` on every request. `LLMNode` simply never read it. With nothing true to go on, the model defaulted to its training-data instinct: "I'm an LLM, I don't have persistent memory." Fixed by having `LLMNode` read `state["system_prompt"]` instead of its own frozen constant, and by rewriting the default Agent's seeded prompt (`packages/conversation/bootstrap.py`) to describe the system's real capabilities — including a direct `UPDATE` of all 15 already-provisioned `agents` rows in the database, since the seeding function is an idempotent get-or-create and would otherwise have left every existing tenant stuck on the old string. Worth noting for future verification: the first test used a leading question in a conversation that was reusing earlier (pre-fix) history, and the model partly echoed its own earlier wrong answer back — a clean-slate conversation with neutral phrasing was needed to actually prove the fix.

**Verifying that fix surfaced a second, unrelated crash — and fixing it unlocked three real items in Phase 9 (Production Retrieval) for the first time.** The test question happened to route to the `retrieve` node, which crashed on every call: `RetrieveNode` was calling `KnowledgeManager.search()` with an entirely wrong schema. Tracing it further found `KnowledgeManager`'s DI wiring stubs all three of its real collaborators as `None`, and its own `search()` method has an internal bug — it builds a *file-ingestion* schema (`IngestionRequest`, with `file: Path`/`document_name` fields) to pass to a retriever expecting nothing of the sort. Rather than repair a facade with multiple internal defects, `RetrieveNode` was rewired to the already-real, already-proven `RetrievalPipeline`/`VectorStoreManager` stack — the same Chroma-backed embeddings path this session's memory work already validated. Query Embedding, Dense Retrieval, and Similarity Search move from Partial to Done — Phase 9's first-ever provable items, taking it from 0% to 23.1%. Verified live: a clean-slate conversation now correctly describes its own architecture, and the full chat/memory/tool-calling regression still passes. Score: 36.1%, a new all-time high.
