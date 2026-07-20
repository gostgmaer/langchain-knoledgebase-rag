# Changelog — this session's fixes

A plain narrative of everything fixed in one continuous working session, in the order it happened. For the current state of the whole system (what's done/partial/broken/pending against the roadmap), see [`docs/BUILD_STATUS.md`](./BUILD_STATUS.md). For the target roadmap itself, see [`docs/mvpRAG.md`](./mvpRAG.md).

---

## Calculator tool crashes

Two separate bugs in `packages/tools/builtin/calculator.py`, both fixed:

- `isinstance(node, ast.Num)` — `ast.Num` was removed in Python 3.14. Deleted the dead branch; the `ast.Constant` check above it already covers numeric literals.
- `response.__dict__` on a `@dataclass(slots=True)` — slotted dataclasses have no `__dict__`, so every single call crashed. Replaced all five call sites with `dataclasses.asdict(response)`.

---

## Planner consolidation

Three separate `GraphPlanner`/`PlannerResult` implementations existed in the codebase (`packages/graph/planner.py`, `packages/graph/nodes/planner.py`, `packages/planner/planner.py`). By request, consolidated onto `packages/planner/planner.py`'s richer, plan-based (`ExecutionPlan`/`ExecutionStep`/`Capability`) model. Wiring it in required:

- Renaming its `plan()` method to `__call__()` and wrapping the return in `{"execution_plan": plan}` — the shape the LangGraph node contract actually expects.
- Finding and fixing a **circular import** the new planner introduced: it imported `GraphState` at module level, which transitively re-imports `packages.planner.planner` itself through `packages.graph`'s own `__init__.py` → `builder` → `nodes` chain. Fixed with the same `TYPE_CHECKING` guard pattern already used elsewhere in this codebase for exactly this reason.
- Rewriting `packages/graph/state.py`'s `execution_plan` field type and `packages/graph/router.py`'s `route()` method to use `plan.has(Capability.RETRIEVAL)` instead of matching a `next_node` enum that no longer existed.
- Deleting both losing duplicates outright — `packages/graph/planner.py` and `packages/graph/nodes/planner.py` — plus `packages/graph/nodessss.py`, an already-orphaned file that only existed to import one of them.

---

## DB session sharing bug

`packages/infrastructure/container/database.py`'s `session` provider was `providers.Resource` — a singleton for the app's entire lifetime, meaning every request shared the exact same `AsyncSession`. Swapped to `providers.Factory` (a new session per resolution). This surfaced two further real problems, both fixed in the same pass:

- **A connection leak.** Naively making `session` a `Factory` meant every repository and the memory store independently opened their *own* fresh, never-closed connection per request. Fixed by rewriting `packages/api/dependencies.py`'s `get_conversation_manager` (later generalized into `request_scoped_session`/`get_scoped_container`) to open exactly one session per request, temporarily `.override()` the whole DI tree onto it, and explicitly close it in a `finally`.
- **A knock-on `TypeError`** in `packages/api/lifespan.py` — `await container.graph.builder()` stopped being valid once the dependency chain became fully synchronous. Fixed by dropping the `await`.

---

## Building `POST /conversations`

`packages/api/routers/conversations.py` was a one-line stub. Built it for real: creates a conversation against an auto-provisioned default `Agent` (and the default `ModelProfile` it references), via new `packages/conversation/bootstrap.py` get-or-create helpers seeded from real `packages.config` AI settings. Confirmed idempotent. Proving this actually persisted data surfaced two more real bugs:

- **DB schema drift.** The real `model_profiles` table (with 1 existing profile, 1 agent, 1 conversation, and 47 messages already in it — not an empty dev DB) was missing its `vector` column entirely, because `Base.metadata.create_all` only creates missing tables, never adds columns to ones that already exist, and this table predates the `vector` column being added to the model. Fixed with an additive `ALTER TABLE model_profiles ADD COLUMN vector vector(1536)`, backfilled the existing row, then `SET NOT NULL` — existing data confirmed untouched before/after.
- **Repository writes never committed.** `packages/infrastructure/repositories/base.py`'s `create()` only ever `flush()`ed, never `commit()`ed. `POST /conversations` returned a real-looking `201`, but the row was silently rolled back the moment its request-scoped session closed. Fixed at the correct boundary — `request_scoped_session` now commits once at the end of a successful request and rolls back on exception, not inside the repository itself (since several repository calls in one request need to share one transaction).

---

## Replacing `ConversationManager` with `ChatService`

By explicit request, `packages/application/services/chat_service.py`'s `ChatService` replaced `ConversationManager`'s flow entirely as the top-level `POST /api/v1/chat` entry point. Getting it working meant finding and fixing **9 real, distinct bugs in one continuous chain** — each only reachable once the previous one was fixed:

1. `packages/graph/nodes/llm.py`'s `LLMNode` called `self._chat.ainvoke(...)` — `ChatService` has no such method.
2. `ConversationService.get_or_create()` called `ConversationRepository.get_by_session_id()`, which didn't exist — added it.
3. `ChatService._update_conversation()` called `ConversationService.touch()`, which didn't exist at all (there was a `touch()` method, but misplaced on `ChatService` itself, never called by anything) — added the real one.
4. Two separate `UnitOfWork` classes existed in the codebase (`packages/infrastructure/repositories/unit_of_work.py`, the rich one with repository properties, vs. `packages/infrastructure/database/transaction.py`, a thin one with none) — the DI container was wired to the thin one. Repointed it to the rich one.
5. `ChatService._execute_runtime()` was a hardcoded stub: `return "Hello! AI Runtime is not connected yet."`. Rewired to genuinely invoke `GraphManager`, so retrieval, tool-calling, and memory extraction all stay intact instead of being bypassed.
6. `packages/chat/chat_service.py` referenced `self._llm.model_name`, which doesn't exist on `LLMManager` — real attribute is `.config.model` (same fix needed for `.provider`, assigned to a `str`-typed field).
7. Gemini returns `AIMessage.content` as a list of content blocks, not a plain string — broke memory-fact JSON parsing (`json.loads` choking on a list).
8. The same list-content issue broke saving the assistant's message to the database (a `Text` column can't hold a list). Fixed at the true source — `LLMNode`, before the message ever enters graph state — via a new shared `packages/shared/messages.py` helper, rather than patching every downstream consumer separately.
9. `ConversationService.touch()`/`close()` used a timezone-*aware* `datetime.now(datetime.UTC)` against a `TIMESTAMP WITHOUT TIME ZONE` column — asyncpg rejected the mismatch. Fixed to use naive UTC datetimes, matching the convention the rest of this model already uses.

**Result:** confirmed live, twice in a row, in the same conversation — a real message in, a real Gemini-generated response out, the second call correctly recalling the first turn's content. The first fully working `POST /api/v1/chat` round trip in this project's history.

---

## Testing conveniences

Specifically to make manual/API testing practical without hand-crafting headers first:

- `X-Tenant-ID`/`X-User-ID` now fall back to fixed default UUIDs when omitted. This required relaxing **three separate places** that were each independently hard-rejecting a missing tenant header before a request could even reach the router: `TenantMiddleware`, `packages/api/security.py`'s `get_tenant_id` (an `APIKeyHeader` with `auto_error=True`), and the router-level check itself.
- `conversation_id` is now optional on `POST /api/v1/chat` — omitting it auto-provisions (idempotently, keyed by tenant+user) a default conversation via a new `ensure_default_conversation` bootstrap helper.

A bare `POST /api/v1/chat {"message": "..."}` with zero headers now works end to end.

---

## Tool-calling was fake

Found by the user, testing their own running server, not by this audit: asked "what about calculator," the app confidently described a "Code Interpreter" and "Google Search" tool — **neither of which exists anywhere in this codebase.** The real registered tools (`calculator`, `get_weather`, `get_news`, `get_google_search`) were correctly in `ToolManager` the whole time, but `LLMNode` never called `.bind_tools()` on the model before invoking it. With no tools bound, the model had zero real tool-calling capability and was purely hallucinating plausible tool names from its training data — a separate, unused `packages/agent/runtime.py`'s `AgentRuntime.run()` had already gotten this pattern right, just never wired into the live path.

Fixed:
- `packages/chat/request.py`'s `ChatRequest` gained a `tools` field.
- `LLMNode` now fetches `tool_manager.list()` and passes it through.
- `packages/chat/chat_service.py`'s `ChatService` binds tools onto the model before invoking, mirroring `AgentRuntime`'s correct pattern.
- Along the way, cleaned up a real naming collision the same file had: two methods both named `chat` (one sync, one async) — Python was silently keeping only the last one defined. Renamed the sync one to `chat_sync`.

**Verified live:** asked to list its tools, the model now names exactly the 4 real registered ones. Asked to "use your calculator tool to compute 847 * 293," the graph genuinely routed to the tool node (`Tool calls detected` → `Calculator Tool Invoked` → `Calculation Successful`) and returned the mathematically correct `248,171` — real delegation, not a guess.

---

## Long-term memory was a functional no-op — now it's real

Asked "what is the status of memory," tracing the pipeline found it ran cleanly but did nothing useful:

- **`PostgresMemoryStore`** (`packages/memory/implementations/postgres_store.py`) was a complete stub. `create()`/`create_many()` built `MemoryFact` objects in Python and just returned them — no `INSERT`, nothing touched the database. The LLM did real work deciding what to remember; it was thrown away immediately.
- **`PgVectorMemoryRetriever`** queried the wrong vector store entirely — the RAG *document* collection (`rag.vectorstore`), not a memories table. Even if anything had been stored, this would never have found it.

Built for real, by request:

- **`packages/domain/models/memory.py`** — a new `Memory` SQLAlchemy model with a genuine `pgvector` column, tenant/user/conversation-scoped.
- **`packages/infrastructure/repositories/memory.py`** — a new `MemoryRepository` with real cosine-similarity search (`Memory.vector.cosine_distance(query_vector)`).
- **`PostgresMemoryStore`** rewritten to actually embed content (via `EmbeddingManager`) and persist through the new repository, for every method (`create`, `update`, `delete`, `search`, `clear`).
- **`PgVectorMemoryRetriever`** rewritten to search the same real table instead of the RAG document store.

Getting this fully working end to end surfaced three more real bugs, each only visible by actually running it, not by reading the code:

1. **Embedding dimension mismatch** — `settings.embedding.dimensions` defaulted to 1536, but the actually-configured model (`gemini-embedding-001`) produces 3072-dimensional vectors. Fixed the default; altered the (still-empty) `memories.vector` column to match.
2. **Postgres enum drift** — expanded `MemoryType` in Python (added `GOAL`/`SKILL`/`PROJECT`, matching what the roadmap's Phase 7 actually asks memory to capture) — but Postgres enum types don't retroactively gain new values just because the Python enum did. The already-created `memorytype` type only knew the original 5. Fixed with `ALTER TYPE memorytype ADD VALUE`.
3. **The significant one: a `Singleton` was caching a database session from before any request ever existed.** `GraphManager` and its entire node chain (`load_memory`, `extract_memory`, `llm`, etc.) were wired as `providers.Singleton` in `packages/infrastructure/container/graph.py` — constructed exactly once, the *first* time anything touched them, which happens at app startup in `lifespan.py`'s graph.png render, long before any request-scoped session override exists. Every memory write after that silently succeeded into that one permanently orphaned, never-committed session from startup — no error thrown, just data that was never visible to anyone, ever. Fixed by converting the entire graph construction chain (`planner`, `load_memory`, `retrieve`, `tool`, `llm`, `extract_memory`, `nodes`, `router`, `builder`, `manager`) and `MemoryManager` itself from `Singleton` to `Factory`, so they're rebuilt fresh inside each request's active session scope — matching how conversations/messages already worked correctly.

**Verified with the strictest test available:** two genuinely separate conversations, zero shared message history. Told the first: "My favorite programming language is Rust and I am building a robotics startup called Ferrolabs." Asked the second, brand new: "What do you know about my programming preferences and my company?" It correctly answered both — pulled from real rows in the `memories` table, found via real pgvector similarity search, confirmed directly in the database.

---

## Episodic memory — the last piece, and it was mostly already built

Asked about the one remaining Partial item, Episodic Memory — the difference from semantic memory (isolated facts) is remembering *what happened*, the narrative of a specific conversation. Tracing it found real, working code that simply had no caller: `LLMMemorySummarizer` and `MemoryManager.summarize()` build a genuine LLM-generated conversation summary, but nothing in the graph ever invoked them.

Fixed:

- **Wired `MemoryManager.summarize()` into `packages/graph/nodes/extract_memory.py`**, called alongside fact extraction on every turn.
- **Made it an upsert, not a blind insert.** By design (confirmed with the user): summarize every turn, but *update* the existing summary rather than pile up a new near-duplicate row each time. Added `MemoryRepository.get_by_conversation_and_type()` and the matching `MemoryStore` interface method; `MemoryManager.summarize()` now checks for an existing `SUMMARY`-typed row for the conversation and updates it in place if found.
- **Fixed a latent bug before it ever fired**: `LLMMemorySummarizer.summarize()` called `response.content.strip()` — the exact same Gemini list-vs-string content bug found and fixed elsewhere this session, just never previously exercised since nothing called this method. Fixed proactively with the same `normalize_message_content()` helper used everywhere else.

**Verified live:** two turns in one conversation — first describing a Rust memory-leak bug, then reporting the root cause found — produced exactly **one** summary row in the database, correctly *updated* on the second turn (not duplicated), whose content captured the whole arc of the conversation rather than just the latest message. Phase 7 (Memory) is now the first phase in this project's history to reach 100%.

---

## The checkpointer msgpack warning — fixed, not just noted

LangGraph's checkpointer had been logging a warning on every single turn:

```
Deserializing unregistered type packages.planner.models.Capability from checkpoint.
This will be blocked in a future version. Set LANGGRAPH_STRICT_MSGPACK=true to block
now, or add to allowed_msgpack_modules to allow explicitly.
```

LangGraph's checkpoint serializer (`JsonPlusSerializer`) uses `ormsgpack` to serialize graph state between steps, including this codebase's own custom types (`Capability`, `ExecutionStep`, `ExecutionPlan` from `packages/planner/models.py`) and a third-party one (`asyncpg.pgproto.pgproto.UUID`). By default it allows any type through with just a warning — but the warning itself says that's changing, and setting `LANGGRAPH_STRICT_MSGPACK=true` (or a future LangGraph default change) would turn this into a hard deserialization failure.

**Fixed** in `packages/graph/builder.py` — instead of `MemorySaver()` with its default serializer, it now constructs one explicitly:

```python
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

_CHECKPOINT_SERDE = JsonPlusSerializer().with_msgpack_allowlist([
    Capability,
    ExecutionStep,
    ExecutionPlan,
    ("asyncpg.pgproto.pgproto", "UUID"),
])

self._checkpointer = MemorySaver(serde=_CHECKPOINT_SERDE)
```

`with_msgpack_allowlist` accepts either an actual class (it derives the `(module, name)` key automatically) or an explicit `(module, name)` tuple — used the tuple form for the third-party asyncpg type since importing its internal `pgproto` module directly felt more fragile than just naming it.

**Verified live:** two full chat turns, zero occurrences of the warning that previously fired on every single one.
