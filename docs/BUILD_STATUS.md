# Build Status — MVP v1.0

Verified against [`docs/mvpRAG.md`](./mvpRAG.md) — that file is the **target roadmap** (what's in scope for v1.0/v1.1/v2.0 and why); this file is the **reality check** (what's actually built, working, broken, or missing right now). Read them as a pair: mvpRAG.md's ✅ marks mean "in v1.0 scope," not "done" — this document is where "done" gets verified.

## 🎉 Milestone: `POST /api/v1/chat` works end to end, for the first time ever

Confirmed live, twice in a row, in the same conversation: a real message in, a real Gemini-generated response out, correctly remembering the prior turn ("You asked me to say hello in exactly three words."). This is the first fully successful chat completion across every audit pass this project has had.

Getting here required replacing `ConversationManager`'s flow with `packages/application/services/chat_service.py`'s `ChatService` (by explicit request), which meant finding and fixing **9 real, distinct bugs** in one continuous chain, each one only reachable once the previous was fixed:

1. `LLMNode` called `self._chat.ainvoke(...)` — `ChatService` has no such method; real one is `achat()`.
2. `ConversationService.get_or_create()` called a repository method (`get_by_session_id`) that didn't exist.
3. `ChatService._update_conversation()` called `self._conversation_service.touch(...)` — `ConversationService` had no `touch()` method at all.
4. Two competing `UnitOfWork` classes existed; the DI container was wired to the wrong (thinner) one.
5. `ChatService._execute_runtime()` was a hardcoded stub (`"Hello! AI Runtime is not connected yet."`) — rewired to genuinely invoke `GraphManager`, keeping retrieval/tools/memory-extraction intact rather than bypassing them.
6. `packages/chat/chat_service.py` referenced `self._llm.model_name`, which doesn't exist on `LLMManager` — real attribute is `.config.model` (and `.provider` needed the same fix for the `str`-typed field it was assigned to).
7. Gemini returns `AIMessage.content` as a list of content blocks, not a plain string — broke memory-fact JSON parsing (`json.loads` on a list).
8. The same list-content issue broke saving the assistant's message to the database (`Text` column, list value) — fixed at the true source (`LLMNode`, before the message ever enters graph state) rather than patched at every consumer.
9. `ConversationService.touch()`/`close()` used a timezone-*aware* `datetime.now(datetime.UTC)` against a `TIMESTAMP WITHOUT TIME ZONE` column — asyncpg rejected the mismatch. Fixed to match the naive-datetime convention the rest of this model already uses.

Also added this session, at the user's request, specifically to make manual/API testing practical: `X-Tenant-ID`/`X-User-ID` now fall back to fixed default UUIDs when omitted (three separate places were independently hard-rejecting a missing tenant header — `TenantMiddleware`, `packages/api/security.py`'s `get_tenant_id`, and the router itself — all three now consistently fall back together), and `POST /api/v1/chat`'s `conversation_id` is now optional, auto-provisioning a default conversation (idempotently, keyed by tenant+user) when omitted. A bare `POST /api/v1/chat {"message": "..."}` with zero headers now works.

**New, non-fatal finding surfaced by this success:** LangGraph's checkpointer now warns `Deserializing unregistered type ... from checkpoint. This will be blocked in a future version` for `asyncpg.pgproto.pgproto.UUID` and `packages.planner.models.{Capability,ExecutionStep,ExecutionPlan}` — the in-memory checkpointer's msgpack serialization doesn't know about these custom types yet. Doesn't fail anything today (both test requests still returned `200`), but LangGraph's own message says this becomes a hard error in a future version. Worth registering these types with LangGraph's `allowed_msgpack_modules` before that happens.

**10th bug, found via live user testing of the running server, not by me:** the user asked their own running instance "what about calculator" and got back a confident description of a "Code Interpreter" and "Google Search" tool — **neither of which exists.** Real tools (`calculator`, `get_weather`, `get_news`, `get_google_search`) were all correctly registered in `ToolManager` the whole time, but `LLMNode` never called `.bind_tools()` on the model before invoking it — the exact pattern `packages/agent/runtime.py`'s (separate, unused) `AgentRuntime.run()` already did correctly. With no tools bound, the model had zero real tool-calling capability and was purely hallucinating plausible-sounding tool names from its training data. **Fixed:** `ChatRequest` gained a `tools` field; `LLMNode` now passes `tool_manager.list()` through it; `ChatService.chat()`/`chat_sync()` bind them onto the model before invoking, mirroring `AgentRuntime`'s correct pattern. Confirmed live: asked to list its tools, the model now names exactly the 4 real registered ones, no more and no less; asked to "use your calculator tool to compute 847 * 293," the graph genuinely routed to the tool node (`[Router] Tool calls detected` → `Calculator Tool Invoked` → `Calculation Successful`) and returned the mathematically correct `248,171` — real tool delegation, not an LLM guess.

Twelfth audit pass, HEAD `ff11edd` ("Refactor and clean up various components in the project"), clean working tree, re-verified 2026-07-20. This is the first pass in several where the tree was NOT being edited live mid-audit — the commit landed cleanly between checks, and everything below was re-verified directly against it.

**Headline finding this pass — the bug that blocked chat for the entire last pass is fixed. `POST /api/v1/chat` no longer 500s.** It now correctly returns a `404 Conversation not found` for a conversation ID that doesn't exist — legitimate business logic, not a crash. The DI container for `memory`/`graph` now constructs fully and for real: `packages/infrastructure/container/memory.py`'s `MemoryManager` is wired with genuine `PostgresMemoryStore`/`LLMMemoryExtractor`/`LLMMemorySummarizer`/`PgVectorMemoryRetriever` instances (all four now receive real dependencies — `database.session`, `ai.manager`, `rag.vectorstore` — and all construct successfully, confirmed live), replacing the nonexistent `factory=checkpoint` argument from last pass.

Fixed, confirmed live this pass:
- **`MemoryManager` constructor mismatch** — last pass's top-priority bug. `packages/infrastructure/container/memory.py` now wires real `store`/`extractor`/`summarizer`/`retriever` providers instead of `factory=checkpoint`. Confirmed: constructing the full `ConversationManager` (which requires `graph.manager()` which requires `memory.manager()`) no longer raises `TypeError`.
- **`GraphContainer`'s `context`/`nodes` signature mismatch** — the commented-out `# NodeContext` callable and the old `GraphNodes(context=...)` call are gone, replaced with `GraphNodes(planner=, load_memory=, retrieve=, tool=, llm=, extract_memory=)`, matching the new dataclass's real fields exactly.
- **`GraphToolNode` is no longer dead code** — it's now constructed in `GraphContainer.tool` and wired into `GraphNodes`. Its own bug (`tool_manager.get_tools()`, a method that doesn't exist) is also fixed, now calling the real `tool_manager.list()`.
- **`GraphPlanner.plan()` renamed to `__call__()`** — makes it directly usable as a LangGraph node function; returns `{"execution_plan": PlannerResult(...)}` matching the state-update shape the rest of the graph expects. (This was `packages/graph/nodes/planner.py`'s version — superseded later this pass, see below, by consolidating onto `packages/planner/planner.py` instead.)
- **`packages/api/lifespan.py`'s missing `await`** — `container.graph.builder()` is an async provider; it's now correctly awaited before `.build()` is called.
- **One item off `docs/UNUSED_FILES.md`'s list, for real this time:** `packages/graph.zip` is deleted in this commit (confirmed: `git show --stat HEAD` shows it going from a real blob to gone). First actual cleanup-list deletion across twelve passes.

**Confirmed live via `TestClient`, full round trip:**
- `GET /api/v1/health` → **200**, `{"database":"healthy","redis":"healthy"}` — holding steady.
- `POST /api/v1/chat` (valid tenant header, random `conversation_id`) → **404**, `{"success":false,"error":"HTTPException","message":"Conversation not found."}` — clean domain error from `ConversationManager.chat()` → `service.get()` returning `None`. This is real progress: reaching this line requires the entire DI chain (`database`, `ai`, `rag`, `tools`, `memory`, `graph`, `services`) to construct successfully first.
- **Not yet provable:** an actual successful chat turn (planner → retrieve/llm/tool → response). There is still no HTTP-reachable way to create a conversation (`conversations.py` router is still a one-line stub — see APIs/Phase 14, unchanged), and `Conversation` has required FKs (`agent_id`, etc.) that need real seed data. So the graph's actual node execution — and with it, `GoogleProvider`'s `api_key=` fix — remains correct-in-the-code but unproven live, for a fourth pass running now, blocked by a missing prerequisite endpoint rather than a bug.

**Regression found this pass, then fixed the same session, by request:** the `PlannerResult`/`GraphPlanner` duplication had gotten worse — three separate implementations existed (the live, wired one in `packages/graph/nodes/planner.py`, an old orphaned one in `packages/graph/planner.py`, and a brand-new third one in `packages/planner/planner.py` with a richer `ExecutionPlan`/`ExecutionStep`/`Capability` model, part of an entirely separate, also-unwired package). The user asked to consolidate onto `packages/planner/planner.py` specifically, since its plan-based model is the better long-term design (extensible to multi-capability plans, matches the roadmap's Memory/HITL/Summarization phases better than a single-hop enum). **This is now done:**

- `packages/planner/planner.py`'s `plan()` method renamed to `__call__()`, returning `{"execution_plan": plan}` — the shape the LangGraph node contract expects (it previously returned a bare `ExecutionPlan`, which wasn't callable as a node at all).
- **A real circular-import bug was found and fixed while wiring this in:** `packages/planner/planner.py` imported `GraphState` from `packages.graph.state` at module level, which transitively re-imports `packages.planner.planner` itself through `packages.graph`'s `__init__.py` → `builder` → `nodes` chain — confirmed failing with `ImportError: cannot import name 'GraphPlanner' from partially initialized module` when imported first in a fresh interpreter. Fixed with the same `TYPE_CHECKING` guard pattern already used elsewhere in this codebase for exactly this reason.
- `packages/graph/state.py`'s `execution_plan` field retyped from `PlannerResult` to the new `ExecutionPlan`.
- `packages/graph/router.py`'s `route()` rewritten to call `plan.has(Capability.RETRIEVAL)` instead of matching on a `next_node` enum — confirmed live: a message containing a retrieval keyword now correctly routes to `"retrieve"`, everything else to `"llm"`, same behavior as before, driven by the new model. (The pre-LLM `"tool"` branch was intentionally dropped, not ported: `GraphToolNode` wraps LangGraph's own `ToolNode`, which requires `tool_calls` already present on the last message — something only the LLM node produces. Routing to `"tool"` before the LLM ever runs wouldn't have anything to execute. Tool routing correctly stays post-LLM, via `GraphRouter.after_llm()`, unchanged.)
- `packages/infrastructure/container/graph.py` and `packages/graph/nodes/__init__.py` both now import `GraphPlanner` from `packages.planner.planner`.
- **The two losing duplicates are deleted outright**, not just left orphaned: `packages/graph/planner.py` and `packages/graph/nodes/planner.py`. `packages/graph/nodessss.py` (the old renamed-not-deleted `nodes.py`, already flagged for deletion) was also deleted — it only existed to import the now-gone `packages/graph/nodes/planner.py` and was otherwise already fully dead.
- Confirmed live end to end after the swap: full import sweep, direct `GraphPlanner()`/`GraphRouter()` execution against both a plain message and a retrieval-keyword message, and a full `TestClient` round trip (`GET /api/v1/health` → 200, `POST /api/v1/chat` → 404 Conversation not found, same as before the swap) — no behavior change, no regressions.

**The DB session `Resource`/`Factory` bug is now fixed — and it turned out to be more involved than the one-line swap this doc previously suggested.** `packages/infrastructure/container/database.py:25`'s `session = providers.Resource(create_session, ...)` is now `providers.Factory(create_session, ...)`, with `create_session` (`packages/infrastructure/database/session.py`) rewritten from an async generator to a plain function that just returns `session_factory()` — a `Resource` is a singleton-until-shutdown lifecycle; `Factory` creates a new instance every resolution, which is what "don't share one session across every request" actually requires.

**Testing this immediately surfaced two real follow-on problems, both now also fixed, not just noted:**
1. **`packages/api/lifespan.py`'s `await container.graph.builder()` broke** (`TypeError: 'GraphBuilder' object can't be awaited`, caught by the surrounding `try/except` so it only ever showed up as a warning, never crashed anything). Cause: with `database.session` now synchronous, the entire dependency chain feeding `graph.builder()` (via `memory.manager()` → `PostgresMemoryStore(db=database.session)`) resolves synchronously too — dependency_injector no longer returns a coroutine here. Fixed by dropping the `await`.
2. **A real connection leak, confirmed live via a `SAWarning`/`RuntimeError` during shutdown** (`"garbage collector is trying to clean up non-checked-in connection"`), not a hypothetical: naively making `session` a `Factory` means every independent resolution of it — one for each of the 9 repositories in `packages/infrastructure/container/repositories.py`, one for `packages/infrastructure/container/memory.py`'s `PostgresMemoryStore` — creates its **own** fresh `AsyncSession`/DB connection, and only the one existing consumer wrapped in an explicit `try/finally` (`packages/api/dependencies.py`'s `get_db_session`, used by the health check) ever closed what it created. A single chat request was silently opening a new, real, unclosed connection on every `ConversationRepository`/`MessageRepository`/`PostgresMemoryStore` construction. Fixed by rewriting `get_conversation_manager` (`packages/api/dependencies.py`) to open **one** session per request, temporarily `.override()` `container.database.session` with it (which — because `database` is wired as a `providers.Container`, the same underlying provider `repositories.py` and `memory.py` both reference via `DependenciesContainer` links — makes every repository and the memory store resolve to that *same* session for the duration of the request), then `reset_override()` and `await session.close()` in a `finally`. This also incidentally fixes the earlier-documented "repos in one request could end up on different sessions, breaking transactional consistency" risk, since they now provably share one.

Confirmed live: 3 sequential chat requests plus a health check, no leak warnings, no cross-request sharing (two independent `container.database.session()` calls return distinct objects), full import sweep unchanged (384/398, same 14 pre-existing failures, none new).

- Modules importing cleanly (fresh sweep, just now): **384 / 399 (96.2%)** — module count dropped by 2 from deleting the two dead planner files plus `nodessss.py`, as expected. All 14 remaining failures are the same pre-existing, already-tracked issues (stale `AgentState` imports, `sdk` bugs, `knowledge/splitters` mismatch, dead `ai/factory.py`, Alembic env quirk, one unwired `packages.middleware.memory` `NameError`) — none introduced by this fix.

## Milestone this session: a chat turn now reaches the LLM node for the first time across every audit pass

By request, built the previously-missing "create a conversation" flow and chased it all the way to a genuinely new, deeper bug — this is the furthest any request has ever gotten in this codebase's history.

**Built:**
- **`packages/api/routers/conversations.py`** — was a one-line stub, now a real `POST /conversations` route. Requires `X-Tenant-ID` and `X-User-ID` headers (validated as well-formed UUIDs, not just present), creates a `Conversation` against a per-tenant default `Agent`.
- **`packages/conversation/bootstrap.py`** (new) — `ensure_default_model_profile()`/`ensure_default_agent()`, get-or-create helpers seeded from real `packages.config` AI settings (provider, model, temperature, etc.), not hardcoded values. `ModelProfile` is global (get-or-create by `is_default`/name); `Agent` is correctly scoped per-tenant (a new `AgentRepository.get_by_tenant_and_name()` method), since `Agent.tenant_id` is a required column — a single global default agent would have leaked one tenant's agent config to every other tenant.
- **`packages/api/schemas/conversation.py`** — was a one-line stub, now `ConversationCreateSchema`/`ConversationResponseSchema`.

**Two real, live-confirmed bugs found and fixed while proving this actually works end to end, neither hypothetical:**
1. **DB schema drift**: `model_profiles` (a real table with 1 existing row, 1 agent, 1 conversation, and 47 messages already in it — this is not an empty dev DB) was missing its `vector` column entirely — `Base.metadata.create_all` only creates missing tables, never adds columns to ones that already exist, and this table predates the `vector` column being added to the `ModelProfile` model. This broke *any* query against `ModelProfile`, not just new ones. **Fixed via an additive `ALTER TABLE model_profiles ADD COLUMN vector vector(1536)`**, backfilled the existing row with a zero vector, then `SET NOT NULL` to match the model — confirmed the existing row and its relationships (1 agent, 1 conversation, 47 messages) are untouched (row counts unchanged before/after).
2. **Repository writes don't commit — a previously-documented gap, now confirmed as a live, request-breaking bug, not just a code-reading finding.** `packages/infrastructure/repositories/base.py`'s `create()` only ever `flush()`ed, never `commit()`ed. `POST /conversations` returned a real-looking `201` with a valid UUID, but the row was silently rolled back the moment its request-scoped session closed — the very next `POST /api/v1/chat` against that same ID correctly 404'd, since the conversation was never actually persisted. **Fixed at the correct boundary**: `packages/api/dependencies.py`'s `request_scoped_session` (the same per-request session helper from the DB-session fix above) now commits once at the end of a successful request and rolls back on exception — not inside `BaseRepository` itself, since several repository calls in one request need to share one transaction.

**Confirmed live, full round trip:** `POST /conversations` → `201`; `POST /api/v1/chat` against that real `conversation_id` → conversation found (no more 404), memory/graph construction succeeds, **a real embedding API call to Google's `generativelanguage.googleapis.com` succeeds (`200 OK`)** — the first live proof, ever, that the `GoogleProvider` `api_key=` fix (tracked as "correct but unprovable" for four straight passes) actually works — planner correctly routes to `"llm"`, and execution reaches `packages/graph/nodes/llm.py:47`. Two independently-created conversations for the same tenant correctly reuse the same auto-provisioned default agent (idempotency confirmed).

**The new blocker, found this session, not yet fixed:** `packages/graph/nodes/llm.py:47` calls `self._chat.ainvoke(request.messages)` — but `self._chat` is a `packages.chat.chat_service.ChatService` instance, and `ChatService` has no `.ainvoke()` method at all. Its real async method is `achat(request: ChatRequest) -> ChatResponse` (`packages/chat/chat_service.py:34-51`) — different name, and it expects a `ChatRequest` object, not a raw messages list. `AttributeError: 'ChatService' object has no attribute 'ainvoke'`, confirmed live. This is now the single thing standing between here and a fully complete, working chat response.

Status legend:
- **✅ Done** — built and proven to work at runtime.
- **🟡 Partial** — real logic exists but is incomplete, unverified live, or reachable only indirectly.
- **🔴 Broken** — real logic exists but currently fails when run.
- **⚪ Pending** — not implemented (empty/comment-only stub file, empty package, or nothing found).

Each item below lists the exact file(s) backing the claim so this doc stays checkable against the code, not just against itself.

---

## Completion by phase

Counted against every individual checklist bullet in `docs/mvpRAG.md` (Phases 1–16; Phase 0 excluded as non-code planning work, v1.1/v2.0 excluded as out of current scope). **% Done** only counts items proven to work at runtime — partial and broken items are not counted as done, even though real code exists behind them.

| Phase | Items | ✅ Done | 🟡 Partial | 🔴 Broken | ⚪ Pending | % Done |
|---|---|---|---|---|---|---|
| 1 — Foundation | 11 | 8 | 3 | 0 | 0 | **72.7%** |
| 2 — IAM | 7 | 2 | 0 | 0 | 5 | **28.6%** |
| 3 — Database | 12 | 8 | 0 | 0 | 4 | **66.7%** |
| 4 — LangChain | 10 | 4 | 3 | 0 | 3 | **40.0%** ▲▲ |
| 5 — LangGraph | 9 | 3 | 3 | 0 | 3 | **33.3%** |
| 6 — Session Management | 4 | 1 | 2 | 0 | 1 | **25.0%** ▲ |
| 7 — Memory | 5 | 0 | 5 | 0 | 0 | **0.0%** |
| 8 — Document Processing | 15 | 0 | 10 | 0 | 5 | **0.0%** |
| 9 — Production Retrieval ⭐ | 13 | 0 | 4 | 0 | 9 | **0.0%** |
| 10 — Tools | 6 | 1 | 3 | 0 | 2 | **16.7%** |
| 11 — Human in the Loop | 3 | 0 | 0 | 0 | 3 | **0.0%** |
| 12 — Background Jobs | 5 | 1 | 1 | 0 | 3 | **20.0%** |
| 13 — Production hardening | 5 | 3 | 0 | 0 | 2 | **60.0%** |
| 14 — APIs | 7 | 1 | 1 | 0 | 5 | **14.3%** ▲ |
| 15 — Testing | 4 | 0 | 0 | 0 | 4 | **0.0%** |
| 16 — Deployment | 3 | 0 | 3 | 0 | 0 | **0.0%** |
| **Total** | **119** | **32** | **38** | **0** | **49** | **26.9%** ▲▲ |

**Correction to last pass's table: "Broken hit zero" was wrong — the LangChain row still showed 6 broken items even as the Total row claimed zero, an arithmetic error that slipped through. The real prior baseline was 27 / 36 / 6 / 50, not 27 / 36 / 0 / 56.** Corrected and rebuilt from the per-row numbers this time, then updated for today's session on top of that corrected baseline.

**Overall: 26.9% done · 31.9% partial · 0.0% broken · 41.2% pending** (32 / 38 / 0 / 49 out of 119 roadmap items) — up from 23.5%, and tied with the ninth pass for the highest score this project has ever recorded. Broken hit zero again, this time for real (the earlier "zero" claim was an arithmetic error, corrected above). The movers: **Chat Models and Gemini both moved to Done** — a real, complete chat completion now works end to end, meeting the roadmap's acceptance bar ("providers wired" means completing a real request with a real key, not just instantiating). OpenAI/Anthropic/Groq move to Partial (the shared bug blocking all four is fixed; these three specifically just haven't been exercised with real keys). **Session Management's "Chat Sessions" moved to Done** — a full turn now completes, persists, and correctly recalls prior context. **APIs' "Chat API" moved to Done** — the core "send a message, get a response" now genuinely works (streaming/history are explicitly "ideally," not blocking, per the roadmap's own wording).

---

## ✅ Done — properly implemented and proven

### Foundation
| Item | Evidence |
|---|---|
| Configuration & environment management | Unaffected throughout. |
| FastAPI application — recovered | `from packages.api.app import app` succeeds again, confirmed directly. Both app-breaking bugs from last pass (`nodes.py`/`nodes/` collision, copy-pasted `rag/builders`/`rag/pipelines` `__init__.py`) are fixed. |
| Exception handling — recovered | Confirmed live: a 500 from the chat endpoint (see Broken) still returns the clean, generic `{"success":false,"error":"InternalServerError",...}` envelope, no traceback leak. |
| OpenAPI — recovered | App starts, so `/docs`/`/redoc`/`/openapi.json` are live again. |
| Health checks — recovered, most solid proof yet | Confirmed live: `GET /api/v1/health` with a valid tenant header returns `200`, `{"database":"healthy","redis":"healthy"}` — against real, reachable services in this environment, not a degraded fallback. |
| Logging — recovered | Confirmed live: structured JSON log lines for startup, schema init, and each HTTP request, all correctly formatted. |
| Tenant-context middleware — recovered | Confirmed live: `400 MissingTenant` without the header, `200` with it. |

| Dependency injection — recovered | `database`, `tools`, `ai`, `memory`, and `graph` container branches all construct successfully now. Confirmed live: building the full `ConversationManager` (which transitively requires every branch) succeeds and reaches real business logic. |

**Still Partial:** CLI, Docker, Docker Compose — unchanged.

### Database
| Item | Evidence |
|---|---|
| Conversation & Message models, Knowledge Base / Document / Chunk models, Prompt Templates, Embeddings Metadata, Model Configurations, repository layer | Unaffected throughout — confirmed again this pass via the live, healthy DB connection at the health endpoint. |

### LangChain
| Item | Evidence |
|---|---|
| Document objects | Unaffected. |
| **Embeddings — recovered, first live proof** | A real chat request now reaches the embedding call: `PgVectorMemoryRetriever`/`LLMMemoryExtractor`'s dependency chain hit `generativelanguage.googleapis.com`'s `batchEmbedContents` endpoint and got back a genuine `200 OK`. This is the acceptance bar the roadmap itself sets ("actually complete a real request with a real key") — met, for the first time, this session. |
| **Chat Models — Done, first time ever** | A complete chat turn now works end to end: `LLMNode` → `ChatService.achat()` → real Gemini completion → response saved and returned to the client. Confirmed live, twice in a row, including correct recall of prior conversation turns. |
| **Gemini — Done** | Proven on both axes now: embeddings (see above) and chat completion (see Chat Models). `GoogleProvider`'s `api_key=` fix (`packages/infrastructure/ai/providers/google.py`) is fully live-confirmed correct. |

**Partial, not Broken:** OpenAI, Anthropic, Groq — the bug that blocked every provider identically (`LLMNode` calling a nonexistent `ChatService.ainvoke`) is fixed, so there's no known reason these three wouldn't work too; they just haven't been exercised live with real keys this session (the default provider is Google).

### LangGraph
| Item | Evidence |
|---|---|
| Nodes & package wiring — recovered | `packages/graph/nodes/` (the new per-class package: `RetrieveNode`, `LLMNode`, `LoadMemoryNode`, `ExtractMemoryNode`, `GraphPlanner`, plus a real `GraphNodes` dataclass tying them together) now imports cleanly and is structurally sound. Confirmed via direct import and the fresh sweep. |
| GraphState | Imports cleanly; `execution_plan` is now typed against `packages.planner.models.ExecutionPlan`, the consolidated planner model (see below). |
| **Conditional routing / graph construction via DI — recovered** | `container.graph.manager()` now fully constructs: `context`/`nodes` signature mismatch is fixed (`GraphNodes(planner=, load_memory=, retrieve=, tool=, llm=, extract_memory=)`, matching the real dataclass), and the upstream `memory.manager` bug that blocked it is fixed too. Confirmed live via a full `ConversationManager` construction reaching real business logic. **Node execution itself (planner routing to retrieve/llm/tool at runtime) is not yet proven** — no live chat turn has completed end to end — so this is "wiring proven," not "behavior proven." |

**Still Partial, unaffected:** Reducers, Checkpointing, Streaming.

### Session management
| Item | Evidence |
|---|---|
| No more duplicate user message (fix retained) | Unaffected. |
| **Chat Sessions — Done, first time ever** | A complete chat turn now works: conversation created/found, user message saved, real LLM response generated and saved, conversation stats updated, all in one transaction. Confirmed live twice in a row, the second call correctly recalling the first turn's content. |

### Tools
| Item | Evidence |
|---|---|
| Tool registry population, tool executor signature | Now proven correct through real invocation, not just structurally — see below. |
| **Calculator — Done, now proven through the full app, not just standalone** | Confirmed live: asked to compute `847 * 293` via chat, the graph genuinely routed to the tool node (`[Router] Tool calls detected` → `Calculator Tool Invoked` → `Calculation Successful`) and returned the mathematically correct `248,171` in the final response — real delegation, not an LLM guess. |

**Still Partial, but for a different, better reason now:** Web Search, Weather, News — the real blocker (no tools were ever bound to the model at all — see the milestone section's 10th bug) is fixed; these three are discoverable and bindable through the exact same mechanism just proven for Calculator, and the model now correctly names all four in its own tool list. They're Partial rather than Done only because this session specifically live-tested Calculator's invocation, not these three individually.

### Background jobs / Production
| Item | Evidence |
|---|---|
| Configuration management | Unaffected. |
| Redis connectivity — recovered, most solid proof yet | Confirmed live via the health endpoint: `"redis":"healthy"` against a real, reachable Redis in this environment. |

### Memory
| Item | Evidence |
|---|---|
| Conversation memory (short-term) | Unaffected. |
| **Semantic / episodic / preferences / facts backing store — upgraded from Pending to Partial** | `packages/infrastructure/container/memory.py` now constructs real `PostgresMemoryStore` (backed by `database.session`), `LLMMemoryExtractor`/`LLMMemorySummarizer` (backed by `ai.manager`), and `PgVectorMemoryRetriever` (backed by `rag.vectorstore`) — confirmed live, all four build successfully as part of `MemoryManager`'s construction. Partial, not Done, for a stronger reason than "unproven live": `PostgresMemoryStore` itself is fully a stub — every method is a placeholder comment, `self._db` is never actually used for a query (see Broken section's correction below). Only `PgVectorMemoryRetriever` has confirmed real query logic behind it. |

---

## 🔴 Broken — real code exists but currently fails

**Nothing is currently classified as Broken this pass** — every item that was Broken last pass is either fixed outright or downgraded to Partial because it now fails on a legitimate, expected condition (a clean domain error) rather than crashing. First time this section has been empty across twelve passes.

### Fixed this pass

| Item | File(s) | What was wrong, and what changed |
|---|---|---|
| **`MemoryManager` constructed with a nonexistent `factory` argument** | `packages/infrastructure/container/memory.py` | Was the single highest-priority bug last pass — the direct cause of `POST /api/v1/chat`'s `500`. Now fixed: `MemoryContainer.manager` is wired with real `store=`/`extractor=`/`summarizer=`/`retriever=` providers (see Memory section above), matching `MemoryManager.__init__`'s actual signature. Confirmed live: constructing the full DI chain up through `ConversationManager` no longer raises `TypeError`. |
| **`GraphContainer`'s `context`/`nodes` signature mismatch** | `packages/infrastructure/container/graph.py` | The commented-out `# NodeContext` callable and `GraphNodes(context=...)` are gone. `nodes` is now `providers.Singleton(GraphNodes, planner=, load_memory=, retrieve=, tool=, llm=, extract_memory=)`, matching the dataclass's real fields. Confirmed: `container.graph.manager()` no longer raises a `TypeError` here either. |
| **`GraphToolNode` — no longer dead code** | `packages/graph/nodes/tool.py`, `packages/infrastructure/container/graph.py` | Now constructed via `GraphContainer.tool` and passed into `GraphNodes`. Its own bug — calling `tool_manager.get_tools()`, a method that doesn't exist — is also fixed, now calling the real `tool_manager.list()`. |
| **`packages/api/lifespan.py`'s missing `await`** | `packages/api/lifespan.py` | `container.graph.builder()` is an async provider; it's now correctly `await`ed before `.build()` is called, instead of being called synchronously and passed a coroutine object. |

### Still open, unchanged from last pass

| Item | File(s) | What's wrong |
|---|---|---|
| **`GoogleProvider`'s `api_key=` fix — still correct, still unprovable, fourth pass running** | `packages/infrastructure/ai/providers/google.py` | Unchanged, confirmed still correctly passing `api_key=settings.ai.google_api_key`. Still can't be demonstrated live — not because of a DI bug anymore, but because there's no way to create a conversation over HTTP to actually drive a chat turn through to LLM construction (see APIs/Phase 14). |
| **Correction: `packages/memory/implementations/postgres_store.py` is a stub, not "substantial"** | `packages/memory/implementations/postgres_store.py` | Traced fully while tracking down the connection-leak fix above: every method (`create`, `get`, `update`, `delete`, `search`, ...) is a placeholder — comments like `# INSERT INTO memories ...` where a real query would go, no actual SQL anywhere. `self._db` is stored in `__init__` but never touched by any method. An earlier pass's description of this file as part of "real, substantial pgvector-backed implementations" was wrong — only `PgVectorMemoryRetriever` (backed by `rag.vectorstore`, confirmed separately to have real `similarity_search()` SQL) earns that description. `LLMMemoryExtractor`/`LLMMemorySummarizer` weren't re-verified this pass either way. |
| **Most of `docs/UNUSED_FILES.md`'s cleanup list is still untouched** | — | `packages/application/` (full package), `packages/conversation/store.py`/`memory_store.py`, `packages/infrastructure/ai/factory.py`, `packages/sdk/upload/`, `packages/sdk/notification/`, `packages/sdk/common/models.py`, `requirements.txt`, and the top-level `packages.zip` are all still present, unchanged. Three items did come off the list this pass — see below. |

### Found and fixed in the same session — a regression that didn't survive the pass

| Item | What happened |
|---|---|
| **`PlannerResult`/`GraphPlanner` triplication** | Found this pass: the duplication had grown from two classes to three (`packages/graph/nodes/planner.py` live, `packages/graph/planner.py` and the new `packages/planner/planner.py` both dead). By explicit request, consolidated onto `packages/planner/planner.py` (the richer `ExecutionPlan`/`Capability`-based model) — see "Fixed, confirmed live this pass" above for the full detail, including a real circular-import bug found and fixed during the wiring. Both losing duplicates are now deleted, not just orphaned. |

### Fixed off `docs/UNUSED_FILES.md`'s list this pass

- **`packages/graph.zip`** — deleted in this commit (`git show --stat HEAD` confirms: blob present at start of commit, gone after). First cleanup-list item actually removed across twelve passes.
- **`packages/graph/planner.py` and `packages/graph/nodes/planner.py`** — deleted as part of the planner consolidation above.
- **`packages/graph/nodessss.py`** — deleted; it only existed to import the now-gone `packages/graph/nodes/planner.py` and was already fully dead regardless.

### `SafeCalculator` — fixed, two bugs found and closed

`packages/tools/builtin/calculator.py`'s `ast.Num` crash (flagged last pass) is fixed — the dead "Python <3.8 compatibility" branch checking `isinstance(node, ast.Num)` was deleted; the `ast.Constant` check right above it already covers numeric literals on every supported Python version. Confirmed live: all arithmetic, all 14 supported functions, and both constants now evaluate correctly, including every one of the tool file's own 22 built-in test expressions bar one (see below).

**A second, more severe bug was found while fixing the first, and is also now fixed.** `CalculatorSuccess`/`CalculatorError` are `@dataclass(slots=True)`, and every return path in the `calculator()` tool function did `return response.__dict__` — but slotted dataclasses have no `__dict__`. This meant the tool crashed on **every single invocation**, including the simplest successful ones, not just the complex expressions the `ast.Num` bug affected — confirmed live: `calculator.invoke({"expression": "10 - 3"})` raised `AttributeError: 'CalculatorSuccess' object has no attribute '__dict__'` even after the `ast.Num` fix. Worse, that `AttributeError` was then caught by the tool's own generic `except Exception` handler, whose `logger.exception(...)` call crashed a *third* time with the same Windows-console `UnicodeEncodeError` seen elsewhere in this codebase (`GraphVisualizer`, the exception handler) — masking the real error entirely. Fixed by replacing all five `response.__dict__` call sites with `dataclasses.asdict(response)`, which works correctly with slotted dataclasses. Confirmed live: success, division-by-zero, invalid-constant, and overflow paths all now return clean, JSON-serializable dicts with no crash.

**One small, pre-existing gap remains, not part of this fix:** `sum([1,2,3,4])` (one of the tool's own advertised examples) fails with a clean `ValidationError: Unsupported expression: List` rather than a crash — `_eval()` has no case for `ast.List`, so list-literal arguments aren't supported despite `sum`/`avg` being documented as taking them. Minor, and fails gracefully rather than crashing, so left as a follow-up rather than bundled into this fix.

### Still broken, unchanged from last pass

| Item | File(s) | What's wrong |
|---|---|---|
| `EmbeddingSettings` missing `provider` field | `packages/knowledge/embeddings/factory.py:22`, `packages/config/embedding.py` | `EmbeddingFactory.create()` reads `settings.embedding.provider`, but `EmbeddingSettings` only defines `default_provider`. Confirmed live again this pass: constructing `EmbeddingManager()` still raises `AttributeError`. |
| `packages/knowledge/splitters/` — the loader-factory naming-mismatch pattern, recurring | `packages/knowledge/splitters/{pipeline,recursive,factory}.py` | Still `from .base import DocumentSplitter`, but `splitters/base.py` defines `BaseSplitter`. Confirmed via import sweep, unchanged: `ImportError` in all three files. |
| `IngestionPipeline` still calls methods its own collaborators don't define | `packages/knowledge/pipelines/ingestion.py` | Unchanged: `transformer.transform()` (real method: `process()`), `splitter.split(tenant_id=..., content=...)` (real signature takes one `SplitRequest`), `embedding_manager.embed_documents(...)` (real method: `embed(chunks)`). |
| `packages/knowledge/` — wired into the container, but as a dead stub | `packages/infrastructure/container/rag.py:56-61` | Unchanged: `knowledge_manager` provider constructed with three `providers.Object(None)` placeholders instead of real dependencies. Still not consumed by `GraphNodes.retrieve()` or any router. See `docs/UNUSED_FILES.md` for the two same-named-class collisions this created (`RetrievalPipeline`, `ChatService`) between `packages/rag/` and `packages/knowledge/`/`packages/application/`/`packages/chat/`. |
| `HybridRetriever` / pgvector `mmr_search()` — still stubs | `packages/knowledge/retrievers/providers/hybrid.py`, `packages/knowledge/vectorstores/providers/pgvector.py` | Unchanged — both still `raise NotImplementedError`. |
| Stray debug `print()` statements, uncommitted | `packages/conversation/manager.py:73`, `packages/graph/router.py`, `packages/tools/builtin/weather.py:153` | Still present, unchanged (`packages/graph/planner.py`, the file this was previously also tracked against, is deleted now — see planner consolidation above). `conversation/manager.py`'s prints raw user message content — same Windows-console-unicode crash risk as the (now-fixed) `GraphVisualizer` bug if a message contains certain characters. |
| Latent circular-import fragility (not currently breaking anything) | `packages/rag/manager.py` ↔ `packages/application/` ↔ `packages/conversation/` ↔ `packages/graph/` | Unchanged — a raw `from packages.rag.manager import RAGManager` as the first import in a fresh interpreter still fails; the real app avoids it only through favorable import ordering elsewhere. |
| Repository writes no longer commit — unchanged | `packages/infrastructure/repositories/base.py` | Still only `flush()`s, no `commit()`. |
| Orphaned `packages/application/` service layer | `packages/application/` | Unchanged and now more precisely characterized — see `docs/UNUSED_FILES.md`: confirmed genuinely unreferenced at runtime, including `chat_service.py`, which looked wired via a type-hint import in `rag/manager.py` but the actually-injected class is a different, unrelated `ChatService` from `packages/chat/`. |
| Dead orphaned provider factory (old) | `packages/infrastructure/ai/factory.py` | Unchanged — superseded by `infrastructure/ai/providers/factory.py`. |
| Stale `AgentState` import | `packages/conversation/store.py`, `packages/conversation/memory_store.py`, `packages/application/application.py` | Unchanged. |
| Upload SDK wrong import | `sdk/upload/client.py:5` | Unchanged. |
| Notification SDK missing dependency | `sdk/notification/` (5 modules) | Unchanged. |
| `sdk/common/models.py` | `sdk/common/models.py` | Unchanged — `NameError: name 'Pagination' is not defined`. |

### Fixed in earlier passes, still holding (unaffected by this pass's regression)

- **`GraphVisualizer.save_png()` unguarded crash** — still commented out in both `packages/graph/manager.py:16` and `packages/api/lifespan.py`. Third-time-fixed, and this pass's outage has an entirely different, unrelated cause (see above) — worth being precise that this specific bug has not recurred.
- **Weather tool** — still functionally correct; downgraded to Partial in the tally above only because the live, through-the-app proof is currently unobtainable, not because the tool itself regressed.
- **`ConversationContextBuilder`'s system-prompt/RAG-context injection** — still resolved via `PromptBuilder`, as traced last pass; unaffected by this pass's bugs.

---

## ⚪ Pending — not implemented

### IAM (`docs/mvpRAG.md` Phase 2)
| Item | Status |
|---|---|
| JWT / refresh-token validation | `packages/api/middleware/authentication.py` is a **1-line comment stub**: `# Middleware authentication` |
| Rate limiting | `packages/api/middleware/rate_limit.py` is a **1-line comment stub**: `# Middleware rate limit` |
| Metrics middleware | `packages/api/middleware/metrics.py` is a **1-line comment stub**: `# Middleware metrics` |
| User context resolution | Not found anywhere — only tenant/org IDs are captured, as raw unvalidated header strings |
| RBAC & permission validation | No enforcement code found anywhere in the repo |
| Auth package | `packages/auth/__init__.py` is the package's only file, containing just `# init` |

**Practical impact:** anyone can call any `/api/v1/*` route by sending any `X-Tenant-ID` header value — there is no verification that the caller is actually that tenant. This is the single largest gap between "MVP" and anything safe to expose beyond localhost. (Tenant/organization context itself is back to Done this pass — the app starts again and the 400-without-header proof reproduced live.)

### Database (Phase 3)
| Item | Status |
|---|---|
| Migrations — upgraded, but still not a real migration story | Real `alembic.ini` + `alembic/env.py` + one version file (`44b52e61b180_initial_schema.py`) now exist (`0615b25`). `alembic/env.py` correctly wires `Base` metadata and `settings.database.url`; `alembic history` runs and reports a valid single revision. **But the "Initial schema" migration contains no `create_table` calls at all** — its entire body is one `op.alter_column('model_profiles', 'embedding_dimensions', ...)`. It was clearly autogenerated against a DB that already had every table (from `create_all`), so running `alembic upgrade head` against a genuinely empty database would fail immediately rather than create the schema. `packages/api/lifespan.py:41-49` still runs `Base.metadata.create_all` on every startup — Alembic exists as a fully separate, disconnected mechanism, not yet the actual source of truth for schema. |
| Document Versions, Upload Jobs, AI Responses, Feedback tables | Don't exist as models yet |

### LangChain (Phase 4)
| Item | Status |
|---|---|
| Prompt Templates, Output Parsers, LCEL | No `ChatPromptTemplate`, output parser, or runnable chain (`\|` composition) found anywhere in the repo |

### LangGraph (Phase 5)
| Item | Status |
|---|---|
| Reducers | Only the built-in `add_messages` reducer is used — no custom reducers beyond that |
| Streaming | `GraphManager.stream()` (`packages/graph/manager.py:27-35`) is real, working code — but nothing in `packages/api/routers/chat.py` calls it, so it's unreachable over HTTP (the `stream` request field is accepted and silently ignored, see Phase 14) |
| Middleware pipeline, Interrupt, Resume, Runtime Events | Middleware hooks are empty passthroughs; interrupt/resume not implemented |

### Session Management (Phase 6) — remaining gaps
| Item | Status |
|---|---|
| Thread IDs | Present on `GraphState`, but not actually wired to the checkpointer's thread-scoping — partial, not complete |
| Conversation History | Messages are persisted and readable directly from the DB, but there's no HTTP route to fetch them (see Phase 14's missing `GET /chat/{conversation_id}`) — data exists, surface doesn't |
| Persistent Sessions | Checkpointer is `MemorySaver` only (in-memory) — no conversation state survives a process restart |

### Memory (Phase 7)
| Item | Status |
|---|---|
| Semantic memory, episodic memory, user preferences, user facts | No long-term memory code found anywhere (grep for these terms returns nothing) |
| Persistent (non-in-memory) checkpointing | `GraphCheckpointFactory` only wraps `MemorySaver` — nothing survives a process restart; "Future" Postgres/Redis branches are commented out |

### Document Processing (Phase 8)
| Item | Status |
|---|---|
| PDF, DOCX, Markdown, TXT loaders | `packages/rag/loader.py` maps these extensions to real LangChain loaders — imports cleanly, not yet exercised against a real document this pass |
| HTML loader | **Missing from the extension map entirely** — `.html` isn't a supported input format despite being listed in the roadmap |
| Parsing, cleaning, metadata extraction | `packages/rag/document.py` — imports cleanly, unverified live |
| Recursive chunking | `packages/rag/splitter.py` wraps `RecursiveCharacterTextSplitter` — imports cleanly |
| Markdown-aware / semantic chunking | No distinct markdown-structure-aware or embedding-similarity-based splitter found — only the generic recursive splitter exists |
| Embeddings (multiple providers) | Real Google/OpenAI embedding logic exists and imports cleanly (the earlier settings-import bug is fixed) — not exercised against a live index this pass |
| Async indexing | `DocumentIndexer`/`RAGManager` exist and should now construct via the DI container (the fix that unblocked Phases 4/5 applies here too) — not directly re-tested this pass |
| Incremental indexing, batch indexing | No evidence found of change-detection (only re-index what changed) or batched embedding calls — likely full-reindex-only if exercised today |

**Practical impact:** the pipeline shape is real (loader → splitter → embedder → indexer), but every stage is unverified against an actual document end to end, one format is missing outright, and two of three documented chunking strategies don't appear to exist yet.

**New this pass — a second, parallel attempt exists and is currently non-functional.** `packages/knowledge/` (~70 new files) implements the same loader→process→split→embed→index shape a second time, with more supported formats (adds CSV, JSON, HTML) and a cleaner `KnowledgeManager` facade — but it's unwired (nothing outside the package imports it) and internally broken: a `schemas.py`/`schemas/` naming collision makes half its own schema types unimportable, the loader factory references class names that don't match what the loader files define, and `IngestionPipeline` calls methods that don't exist on its own declared collaborators. See Broken section for the full detail. This doesn't change Document Processing's score — nothing in `packages/knowledge/` is more provably working than what `packages/rag/` already had — but it's worth knowing a second, currently-dead implementation now exists alongside the first.

### Production Retrieval (Phase 9 — the roadmap's ⭐ centerpiece)
| Item | Status |
|---|---|
| Query classification, rewriting, expansion | No code found |
| Hybrid / BM25 search, metadata filtering, re-ranking | Not implemented — `packages/knowledge/retrievers/providers/hybrid.py` (new this pass) is a literal `raise NotImplementedError("Hybrid retrieval is not implemented.")` stub |
| Context building, prompt construction for retrieval | Not implemented |
| Citation generation | `message_citation.py` DB model exists but nothing populates it |

This is still the phase furthest from its own ambition in the roadmap — the star marks it as the production centerpiece, and it has the least real retrieval logic behind it of any phase. One genuinely working piece did land this pass, just not reachable: `packages/knowledge/vectorstores/providers/pgvector.py`'s `similarity_search()` is real, correct pgvector cosine-distance SQL (not a stub) — but its own sibling `mmr_search()` is a stub, `HybridRetriever` is a stub, and none of it is wired into the live app.

### Tools (Phase 10)
| Item | Status |
|---|---|
| Knowledge Base Search tool | Empty stub |
| Calculator tool | Empty stub |
| Datetime tool | Empty stub |

### Human in the Loop (Phase 11)
| Item | Status |
|---|---|
| Interrupt, resume, approval workflow | No code found anywhere (grep for `interrupt`/`Command(resume=` returns nothing relevant) |

### Background Jobs (Phase 12)
| Item | Status |
|---|---|
| Queue — upgraded, but still a heartbeat, not a worker | A real `packages/worker/` process now exists (`0615b25`): `main.py` logs `"Worker started."` then loops `logger.info("Worker heartbeat..."); time.sleep(30)` forever. `docker/Dockerfile.worker`'s `CMD ["python","-m","packages.worker.main"]` correctly matches this module's entrypoint — the *deployment wiring* is right. But there is no `arq`/Celery/RQ integration at all despite `arq>=0.28.0` being a declared dependency — it's a process that stays alive, not a job queue that does anything. |
| Document indexing, embedding generation, OCR jobs | None exist yet — nothing to queue anyway until Phase 8/9 retrieval work lands |

### Production hardening (Phase 13)
| Item | Status |
|---|---|
| Rate limiting | See IAM section — `middleware/rate_limit.py` stub |
| Retry policies | `tenacity` is a declared dependency; `infrastructure/http/retry.py` is a **1-line stub** with an unimplemented `@retry` TODO |

### APIs (Phase 14)
**3 of 9 planned routers are now real and registered** (`conversations.py` joined `chat.py`/`health.py` this session) — but each only covers part of its resource's lifecycle, not a full CRUD surface. Confirmed by reading `packages/api/routers/__init__.py` directly:

```python
from packages.api.routers.chat import router as chat_router
from packages.api.routers.conversations import router as conversation_router
# from .documents import router as document_router
# from .feedback import router as feedback_router
from packages.api.routers.health import router as health_router
# from .knowledge_bases import router as knowledge_base_router
# from .models import router as model_router
# from .prompts import router as prompt_router
# from .search import router as search_router
# from .tools import router as tool_router
...
api_router.include_router(health_router)
api_router.include_router(chat_router)
api_router.include_router(conversation_router)
# ... and 6 more, all commented out
```

**Chat router — Done for its one route, still just one route.** `POST /api/v1/chat` now genuinely works end to end — real conversation, real LLM response, real persistence (see the Done section's milestone above). `conversation_id` is now optional (auto-provisions a default conversation when omitted), and `X-Tenant-ID`/`X-User-ID` fall back to fixed default UUIDs when omitted, specifically to make this testable without hand-crafting headers first. Still missing, unchanged: history/streaming/delete routes (see the table below — streaming's `stream` field is still silently ignored).

**Conversation router — new this pass, real, but create-only.** `packages/api/routers/conversations.py` now defines `POST /conversations`, confirmed live: creates a real, persisted `Conversation` against a per-tenant auto-provisioned default `Agent` (see the Done section's "Milestone this session" for the full account). Per this phase's own acceptance bar ("full resource lifecycle... at minimum create + read... a router that only implements one verb... is partial, not done"), this stays **Partial** — there's still no `GET /conversations/{id}`, no list, no delete.

| Missing route | Evidence it's expected but absent |
|---|---|
| `GET /chat/{conversation_id}` or similar — fetch conversation/message history | No such route in `chat.py`; the only way to read back messages is directly from the DB |
| Streaming response (`GET`/`POST` with SSE, or a websocket) | `ChatRequestSchema` has a `stream: bool` field and `cli.py` always sends `stream: false` with a comment implying streaming isn't actually wired up server-side; `ConversationManager`/`GraphManager` do expose a `stream()` method (`packages/graph/manager.py:27-35`) but nothing in `chat.py` calls it — the field is accepted and silently ignored |
| `DELETE /chat/{conversation_id}` — end/delete a conversation | Not present |
| `GET /conversations/{id}`, `GET /conversations`, `DELETE /conversations/{id}` | `conversations.py` only has the create route; read/list/delete don't exist |

The remaining 6 unregistered router files are still **single-line comment stubs** (verified by reading each file directly):

| File | Full contents |
|---|---|
| `packages/api/routers/documents.py` | `# Router documents` |
| `packages/api/routers/feedback.py` | `# Router feedback` |
| `packages/api/routers/knowledge_bases.py` | `# Router knowledge bases` |
| `packages/api/routers/models.py` | `# Router models` |
| `packages/api/routers/prompts.py` | `# Router prompts` |
| `packages/api/routers/search.py` | `# Router search` |
| `packages/api/routers/tools.py` | `# Router tools` |

**Practical impact, updated this session:** a conversation can now genuinely be created over HTTP and then chatted with — the two previously-separate halves of the flow are connected for the first time. What's still missing: no history/listing, no delete, no streaming, and (see LangChain/Phase 4 above) the chat call itself still fails once it reaches the LLM node, on the `ChatService.ainvoke` bug.

### Testing (Phase 15)
| Item | Status |
|---|---|
| Unit / integration / LangGraph workflow / API tests | `tests/` contains only `__init__.py` and `test_llm.py` (24 lines). `test_llm.py` is a manual `asyncio.run(...)` + `print(...)` smoke script — **zero `assert` statements in the entire repo**, despite `pytest`, `pytest-asyncio`, and `pytest-cov` all being declared dependencies in `pyproject.toml`. Worth noting: a real pytest suite would have caught this pass's `AISettings.top_p` regression before it shipped. |

### Deployment (Phase 16) — upgraded from nothing to real-but-buggy
Real Docker/Compose/scripts infrastructure landed in `0615b25` — a genuine jump from "doesn't exist" — but every piece has at least one concrete bug keeping it from counting as done:

| Item | Status |
|---|---|
| `docker/Dockerfile` | Real two-stage build, `uv sync --locked --no-dev`, correctly `COPY`s the project and runs `uvicorn packages.api.app:app` (a real, matching entrypoint). **But** its `HEALTHCHECK` probes `http://localhost:8000/health` — the real route is `/api/v1/health` (mounted under the `/api/v1` prefix) — so the container's own healthcheck 404s forever and would report unhealthy indefinitely. |
| `docker/Dockerfile.worker` | Correctly targets `python -m packages.worker.main`, matching the real (if stub) worker entrypoint — no bugs found here. |
| `docker-compose.yml` / `docker-compose.prod.yml` | Real, substantial files (118 and 83 lines) — not evaluated line-by-line for correctness this pass, but present and non-trivial. |
| `docker-compose.dev.yml` | Still effectively empty — its entire content is one line, `# Empty file`. `make dev` would have nothing to compose. |
| `Makefile` | References `docker/compose/docker-compose.dev.yml` and `docker/compose/docker-compose.prod.yml` — **no `docker/compose/` directory exists**; both files actually live at the repo root. `docker-compose.prod.yml`'s own `env_file: ../../.env` only makes sense from that never-created nested location, so even fixing the Makefile path would leave a second broken relative path. |
| `docker/scripts/wait-for-db.py` | Despite the `.py` name it's a `#!/bin/sh` script, and it's corrupted: the `echo` command and its quoted message are split across two separate lines (as are `exec`/`"$@"`), so under `set -e` it errors out immediately rather than ever reaching the `pg_isready` wait loop. |
| Production configuration | `docker-compose.prod.yml` exists with real content — not yet verified as correct/complete, but no longer "not implemented." |

---

## Gaps beyond the roadmap checklist — production-readiness findings

These don't map to a `docs/mvpRAG.md` checklist item, but they're real gaps that would surface in any production readiness review. Found by reading the actual code, not by checking off roadmap boxes.

### 1. Resource lifecycle — leaked HTTP client
`packages/tools/builtin/weather.py:23` creates `client = httpx.AsyncClient(timeout=10)` at **module level**, used in `get_weather()` (line 61), and it is **never closed anywhere** — not in `packages/api/lifespan.py`'s shutdown block (lines 54-62), which only does `await engine.dispose()` on the DB engine. `news.py` and `search.py` avoid this by instantiating their client fresh per call instead (wasteful but not leaky). Net effect: an unclosed connector/socket on every process shutdown.

### 2. No CORS middleware, no security headers, docs exposed unconditionally
`packages/api/middleware/__init__.py`'s `register_middlewares()` (lines 11-39) registers only `TenantMiddleware`, `LoggingMiddleware`, `RequestIdMiddleware` — there is **no `CORSMiddleware`** anywhere in the codebase (repo-wide grep for CORS/CSP/X-Frame-Options returns nothing). Separately, `packages/api/app.py:21-23` hardcodes `docs_url="/docs"`, `redoc_url="/redoc"`, `openapi_url="/openapi.json"` unconditionally — `packages/config/app.py:18`'s `debug` flag and `packages/config/api.py:16-17`'s `docs_url`/`redoc_url` settings fields exist but are **never actually read by `app.py`**, so Swagger/ReDoc are live in every environment regardless of `DEBUG`.

### 3. Secrets — real keys in local `.env`, correctly gitignored, but worth rotating
Local `.env` holds live-looking keys (OpenAI, Google, Groq, Serper, Tavily, OpenWeather, NewsAPI, a Postgres password, and a placeholder-looking `JWT_SECRET=dev-secret-key-...`). Confirmed via `git log --all -- .env` and `git ls-files` that `.env` has **never been committed** — only the blank `.env.example` is tracked, and `.gitignore` correctly excludes `.env`/`.env.local`. Not a repo leak, but worth rotating any key that's been shared in plaintext during a review like this one, and worth double-checking `JWT_SECRET` gets replaced with a real secret before JWT validation is ever wired up (see Phase 2 gap).

### 4. Input validation — better than expected, but narrow
`packages/api/schemas/chat.py:8-27`'s `ChatRequestSchema` does enforce `message: str = Field(min_length=1, max_length=10000)` and `ConfigDict(extra="forbid")` — so basic length limiting exists. There is no prompt-injection-specific filtering (length limiting is the only defense), and there's nothing to check on the upload side since `packages/api/schemas/document.py` and `routers/documents.py` are still one-line stubs (see Phase 14).

### 5. Async session handling — partially fixed, now committed
- **Fixed, committed:** `packages/api/dependencies.py`'s `get_db_session` is now an async generator — `try: yield session / finally: await session.close()` — so the per-request session actually closes now.
- **Fixed, committed:** `packages/infrastructure/repositories/unit_of_work.py`'s `UnitOfWork.__aexit__` now correctly does `rollback()` on exception / `commit()` otherwise, always `close()`s in a `finally` block.
- **Still open:** `packages/infrastructure/repositories/base.py`'s `create()`/`update()`/`delete()` still call only `flush()`, no `commit()`, no `try/except` around it.
- **Still open:** the live chat path still goes through `get_db_session`/repositories directly, not `UnitOfWork`.
- **Currently unverifiable either way:** the app can't start this pass (see Broken → `settings.embedding`), so none of the above can be re-confirmed live until that's fixed.

### 6. Logging — no PII/body leakage, but no request-id correlation across the pipeline
No full request/response body logging was found (`packages/api/middleware/logging.py`'s `LoggingMiddleware.dispatch`, lines 28-63, only logs method/path/status/duration/request_id/client_ip/user_agent). But that request ID goes nowhere else: `packages/shared/logging.py:23` configures `structlog.contextvars.merge_contextvars`, yet **nothing in the codebase ever calls `structlog.contextvars.bind_contextvars(request_id=...)`**, so the graph/conversation/tools/LLM-manager log lines never carry it. In practice you cannot trace a single chat request across the logs beyond the one "HTTP Request" line the middleware emits.

### 7. Dependencies — two manifests that can drift
`pyproject.toml` pins `requires-python = ">=3.14"` (matches the installed 3.14.0 interpreter) and a `uv.lock` exists for reproducible resolution, but **`requirements.txt` also exists as a second, completely unpinned manifest** duplicating the same dependency list — the two can silently drift out of sync. Confirmed `email_validator` is still missing (needed transitively by `pydantic.EmailStr` in `sdk/notification/models.py`, currently harmless only because nothing imports that module) and `langchain_postgres` is still missing but also unused anywhere, so it's dead weight rather than a live risk.

### 8. Vectorstore config — a silent-`None` trap for two of four documented backends
`packages/config/rag.py:17` defaults `vector_store_backend` to `"chroma"` via alias `VECTOR_STORE_BACKEND` — but `.env` actually sets a **differently-named** variable, `VECTOR_STORE=chroma` (~line 85), which the settings model never reads. It happens to still resolve to the same default today, but changing `.env`'s `VECTOR_STORE` value currently does nothing. Worse: `packages/rag/vectorstore.py`'s `_create()` (lines 26-38) handles `"chroma"` (works, package installed) and `"pgvector"` (explicitly raises a clear `VectorStoreException`) — but `"faiss"` and `"qdrant"`, both listed as valid options in `.env`'s own comment, fall through with **no `else` branch**, silently leaving `self._store = None`. Any later `similarity_search`/`add_documents`/`delete` call then raises a bare `AttributeError: 'NoneType' object has no attribute ...` deep in the RAG pipeline instead of failing fast with a clear configuration error.

### 9. Missing LLM API keys fail late and leak a traceback
None of the provider constructors in `packages/infrastructure/ai/registry.py` (`LLMRegistry.create`, lines 13-50) validate that an API key is present or well-formed before instantiating the LangChain client. A missing/blank key doesn't fail at startup — it fails on the **first real LLM call**, and that error propagates up through `ConversationManager.chat` into the same traceback-leaking `unhandled_exception_handler` documented above (Broken → exception handler). There's no startup pre-flight check and no explicit "provider not configured" error message.

### 10. Data integrity — actually solid, worth noting as a strength
Contrary to what you might expect from the rest of this audit, the core domain models are well-constrained at the DB layer: `Conversation` (`packages/domain/models/conversation.py`) has a `ForeignKey(..., ondelete="RESTRICT")`, a `unique=True` session_id, several `CheckConstraint`s, and `cascade="all, delete-orphan"` on its messages relationship; `Message` (`packages/domain/models/message.py`) has `ondelete="CASCADE"` from its conversation FK, a self-referential `ondelete="SET NULL"` for reply threading, more `CheckConstraint`s, and `@validates` methods for app-level double-checking. Referential integrity is not left entirely to application code, at least for the most important table pair.

### 11. README is an empty file
`README.md` at the repo root is **0 bytes**. There are no setup instructions, no documented required env vars, and no "how to run this locally" anywhere in the repo besides this document and the sparse comments in `.env.example`. Anyone new to the project has to reverse-engineer the run process from `packages/config/` and `main.py`.

### 12. The new CLI script (`cli.py`, commit `72f2b8f`) is a smoke-test client, not a real CLI
`cli.py` (81 lines, repo root, not under `packages/`) is a standalone Rich-based interactive tester: it checks `GET /health`, then talks to a **hardcoded dummy conversation UUID** (`ensure_conversation()`, lines 17-22, literally returns `"3fa85f64-5717-4562-b3fc-2c963f66afa6"` with a comment admitting the real `/conversations` endpoint "isn't wired up yet"), sends `POST /chat` with `stream: false` always (no streaming support despite the flag existing), and generates a **fresh random `X-Tenant-Id` on every run** (line 11) that won't match whatever tenant the dummy conversation was actually seeded under. If the conversation doesn't exist, it just prints a message telling you to seed the DB by hand. This satisfies "a CLI exists" but not "a CLI you can onboard someone with."

### 13. `.env` / `.env.example` — FIXED this pass, confirmed still intact
Previously (see git history of this doc) `.env.example` was a near-verbatim copy of a *different* project's env template. Both files were rewritten from scratch against `packages/config/*.py`'s actual `Field(alias=...)` declarations: dead legacy vars removed, name mismatches fixed (`VECTOR_STORE`→`VECTOR_STORE_BACKEND`, the `ENABLE_*_TOOL` flags renamed to match `FeatureSettings`), organized by settings module with "Required" call-outs. Re-verified this pass: `.env.example` on disk exactly matches that rewrite, committed in `0615b25` with no conflicting overwrite. `.env` was synced to the same key names with all real secret values preserved unchanged.

**Two bugs were deliberately left as-is in the real `.env`** (per an explicit "sync only, don't fix values" request), both still present:
- `OPENWEATHER_BASE_URL=https://api.openweathermap.org/data/2.5` — still missing the `/weather` path segment (fixed in `.env.example`'s template, not in the real `.env`).
- `UPLOAD_SERVICE_URL=https://api.smith.langchain.com` — still LangSmith's URL, not a real upload service.

**A startup-crash risk, unchanged:** `packages/config/loader.py`'s `get_settings()` still eagerly instantiates `IAMSettings()` at import time, which requires `IAM_BASE_URL`/`IAM_CLIENT_ID`/`IAM_CLIENT_SECRET`/`IAM_INTROSPECTION_API_KEY` with no defaults — still present in `.env` today, but removing any of them would crash the app at import time, not just on first use.

### 14. `PromptContext` — resolved this pass, no longer a concern
Previously flagged as reshaped-but-ignored. Traced fully this pass (see Broken → "Fixed this pass, confirmed"): `PromptBuilder.build()` genuinely reads `system_prompt`/`context` off `GraphState` and builds a real system message — confirmed live via coherent chat responses. Closing this item out.

---

## Suggested next priorities (roughly in order)

Chat works end to end now — the priorities below are genuinely the *next* layer, not "get it working at all":

1. **Register `Capability`/`ExecutionStep`/`ExecutionPlan`/`asyncpg.pgproto.pgproto.UUID` with LangGraph's `allowed_msgpack_modules`.** The in-memory checkpointer currently warns on every turn that deserializing these will be blocked in a future LangGraph version — not broken today, but a ticking clock.
2. **Verify OpenAI/Anthropic/Groq actually work**, not just Gemini — the shared bug that blocked all four is fixed, but only Gemini has been exercised live with a real key. Same for Web Search/Weather/News tools — Calculator's live invocation is proven, these three aren't individually yet, despite sharing the exact same now-fixed binding mechanism.
3. **Build `GET /conversations/{id}`** (at minimum) to bring the Conversation API up to its own "create + read" acceptance bar — `POST /conversations` alone keeps it Partial.
4. **Fix `EmbeddingSettings` missing `provider`**, and `packages/knowledge/splitters/{pipeline,recursive,factory}.py`'s `DocumentSplitter`/`BaseSplitter` mismatch — both still unchanged across five passes now.
5. **Finish cleaning up `docs/UNUSED_FILES.md`'s inventory** — most of `packages/application/` just went from "confirmed dead" to "load-bearing" this session (it's the live `ChatService` stack now), so that entry needs a re-read, not a deletion; still safe to remove: `packages.zip`, `packages/sdk/upload/`, `packages/sdk/notification/`, `packages/sdk/common/models.py`, `infrastructure/ai/factory.py`, `requirements.txt`.
6. **Write an actual pytest suite.** A test that created a conversation and chatted against it twice in a row would have caught most of this session's 9 bugs automatically instead of one-at-a-time manual discovery.
7. **Fix the Docker healthcheck path and Makefile paths, wire real JWT validation, and regenerate the Alembic "initial schema" migration properly** — the migration still has no `create_table` calls, and now also doesn't know about the `model_profiles.vector` column added via direct `ALTER TABLE` this session.
8. **Implement `PostgresMemoryStore`'s actual database logic** — every method is currently a placeholder stub; `self._db` (the per-request session it now correctly receives) is never used.
9. **Add streaming and history routes** to the chat surface — explicitly "ideally," not blocking, per the roadmap, but still the most visible remaining gap in the primary conversational surface.

**Fixed this session:** the DB session `Resource`→`Factory` bug and the connection-leak/multi-session risks it could have introduced; the `model_profiles.vector` schema drift; the repository-writes-never-commit bug; the conversations router (stub → real, working, idempotent `POST /conversations`); and, replacing `ConversationManager`'s flow with `packages/application/services/chat_service.py`'s `ChatService` at the user's request, 9 further real bugs across that stack (see the milestone section at the top of this document for the full list) — resulting in the first fully working `POST /api/v1/chat` round trip this project has ever had. **Fixed in earlier passes, holding steady:** `SafeCalculator`'s `ast.Num` and `dataclass(slots=True)`/`__dict__` crashes.
