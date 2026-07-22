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

---

## Prompt Templates, Output Parsers, LCEL — closing LangChain's last gap

By request: LangChain's Phase 4 had three items stuck on Pending — "No `ChatPromptTemplate`, output parser, or runnable chain (`|` composition) found anywhere in the repo." Everything in the codebase was building prompts via f-string concatenation and parsing LLM output via bare `json.loads()`. Fixed by making three components genuinely LangChain-idiomatic instead of hand-rolled:

- **`packages/prompts/builder.py`'s `PromptBuilder`** rewritten to build a real `ChatPromptTemplate` (with a `MessagesPlaceholder` for conversation history) and return `template.invoke(variables).to_messages()`, instead of hand-concatenating f-strings. The external signature/return type (`list[BaseMessage]`) is unchanged, so no caller needed updates.
- **New `packages/memory/implementations/output_parser.py`**: `MemoryFactListParser`, a real `BaseOutputParser[list[dict]]` subclass. `.parse(text)` strips markdown code fences and does `json.loads()`, raising a proper `OutputParserException` on malformed output instead of letting a bare `json.loads()` crash uncaught.
- **`packages/memory/implementations/llm_extractor.py`** and **`llm_summarizer.py`** rewritten around module-level `ChatPromptTemplate.from_messages([...])` prompts and real LCEL chains: `self._chain = _EXTRACTION_PROMPT | llm.model | MemoryFactListParser()` for extraction, `self._chain = _SUMMARY_PROMPT | llm.model` for summarization — replacing manual prompt-string building followed by a bare `.ainvoke()` call.

Wiring this up surfaced one more real bug: both classes were constructed with `llm=` this codebase's own `LLMManager` wrapper, but type-hinted as `llm: BaseChatModel` — a lie the type checker never caught, because nothing had ever tried to actually compose it with `|` before. Trying `_EXTRACTION_PROMPT | llm` raised `TypeError: Expected a Runnable, callable or dict. Instead got an unsupported type: <class 'packages.infrastructure.ai.manager.LLMManager'>` — `LLMManager` is a custom wrapper, not a real LangChain `Runnable`. Fixed by using `llm.model` (a real `LLMManager` property that exposes the genuine underlying LangChain chat model) for the chain, and correcting both type hints to `LLMManager`.

Also discovered along the way: LangChain's own `AIMessage.text`/`Generation.text` (a `TextAccessor`, a genuine `str` subclass) already normalizes provider-specific multi-block message content — e.g., Gemini's list-of-blocks `.content` — into a plain string. `llm_summarizer.py` now uses `response.text.strip()` idiomatically instead of the manual `normalize_message_content()` helper built earlier this session to work around the same problem.

**Verified live:** full import sweep clean (390 OK, same 14 pre-existing unrelated failures, no new ones), plus a full regression covering a normal chat turn, cross-conversation memory recall (correctly recalling both the Rust preference and Ferrolabs technical details), and a real tool-calling request (`55 * 11 = 605`) — all three still passing after the rewrite. LangChain (Phase 4) moved from 40% to 70%.

---

## The system prompt was a lie, and the model believed it

Asked to check the running app's own claim — it had just told the user, confidently, that the system has no persistent memory and clears everything at session end. That's false: this session already built and live-verified a real, persistent, cross-conversation memory pipeline. Tracing why the model would say that found a real bug, not a model quirk.

`packages/infrastructure/container/graph.py:60-66` wired `LLMNode` with `system_prompt="You are a helpful assistant."` — a fixed string frozen in at DI-construction time. Meanwhile `packages/application/services/chat_service.py:109-123` was already doing the right thing: fetching the real `Agent` row and setting `state["system_prompt"] = agent.system_prompt` on every request. `LLMNode` just never read it — it used its own constructor-injected constant instead, so the correct, per-tenant prompt sitting right there in `GraphState` was silently discarded on every single turn. With nothing genuine to go on, the model fell back on its training-data default: "I'm an LLM, I don't have persistent memory."

Fixed in two places:
- `LLMNode.__call__` now reads `state["system_prompt"]` instead of a constructor parameter; the now-unused `system_prompt` constructor arg and its DI wiring were removed.
- `packages/conversation/bootstrap.py`'s default Agent seed (`ensure_default_agent`) now describes the real capabilities — persistent memory, tool access — instead of the generic placeholder string. Since this is an idempotent get-or-create, the already-provisioned rows needed a direct `UPDATE agents SET system_prompt = ...` too, or every existing tenant would have stayed frozen on the old string.

**A leading question can still beat a correct system prompt.** First verification attempt used a heavily leading phrasing ("is this system configured for session-based memory only...?") in a conversation that, on a later turn, was *reusing* an earlier test's history — the model partly echoed its own earlier (pre-fix) wrong answer back ("as I mentioned"). A clean-slate conversation with a neutral phrasing ("what do you know about how your own memory works?") got the fully correct answer: persistent storage, semantic retrieval, contextual continuity — worth remembering that testing a system-prompt fix needs a fresh conversation and neutral wording, not a leading one, to actually isolate what the prompt is doing.

**A second, unrelated crash surfaced verifying the fix — and fixing it unlocked three real Phase 9 items.** The test question happened to route to the `retrieve` node, which crashed every time: `packages/graph/nodes/retrieve.py` called `KnowledgeManager.search()` with the wrong schema (`SearchRequest` instead of `SearchFilter`, wrong kwargs, wrong response shape). Chasing it further found `KnowledgeManager`'s DI wiring (`packages/infrastructure/container/rag.py`) stubs all three of its real collaborators as `providers.Object(None)`, and `KnowledgeManager.search()` itself has an internal bug — it builds an `IngestionRequest` (a *file-ingestion* schema, with `file: Path`/`document_name` fields) to pass to a retriever that expects nothing of the sort. Rather than repair a facade with multiple internal defects, `RetrieveNode` was rewired to the already-real, already-proven `RetrievalPipeline`/`VectorStoreManager` stack — the same Chroma-backed embeddings path this session's memory work already validated — sidestepping `KnowledgeManager` entirely. Also fixed a related type bug in `PromptBuilder`: `context` is a `list[str]` (per `GraphState`), not a `str` — it was being interpolated into the prompt unjoined.

**Verified live:** a clean-slate conversation now correctly and accurately describes its own memory architecture; full import sweep clean; full regression (chat, cross-conversation recall, tool-calling) all still passing. Production Retrieval (Phase 9) gains its first-ever Done items — Query Embedding, Dense Retrieval, Similarity Search — moving from 0% to 23.1%. Overall score: 36.1%, a new all-time high.

---

## Web Search, Weather, News — proving the other three tools, not just Calculator

The priorities list had flagged this explicitly: Calculator's live invocation through the full chat pipeline was proven earlier this session, but Web Search, Weather, and News shared the exact same fix (real tool-binding via `.bind_tools()`) without ever being individually exercised. No code was broken here — just unverified.

All three API keys (`weather_api_key`, `serper_api_key`, `tavily_api_key`) were already configured. Live-tested each through a real chat request, with a fresh conversation per tool to avoid any cross-contamination:

- **Weather** — asked to check London's weather, the model delegated to `get_weather`, which made a real `GET https://api.openweathermap.org/...` call (`200 OK`, confirmed in logs) and returned genuine live data: 22.44°C, clear, 48% humidity, matching the actual API response.
- **Web Search** — asked who won the most recent Formula 1 race, the model delegated to `get_google_search` (`GoogleSerperAPIWrapper`) and returned a specific, current, correctly-dated real-world result — not a generic or stale training-data guess.
- **News** — asked for the latest AI news, the model delegated to `get_news` (Tavily-backed) and returned multiple specific, current headlines with real named companies and products.

All four registered tools (Calculator, Weather, Web Search, News) are now individually live-verified through the full chat pipeline. Also cleaned up two stale leftovers found along the way: `docs/BUILD_STATUS.md`'s Phase 10 "Pending" section still listed "Calculator tool | Empty stub" — false, and out of sync with the Done section just above it — and an old note from several passes back still described the Weather tool as "downgraded to Partial... live proof currently unobtainable," which no longer reflected reality.

**Verified live:** three separate chat requests, three real external API calls, three correct real-world answers. Tools (Phase 10) moves from 16.7% to 66.7% — only Knowledge Base Search and Document Search remain, both still empty stubs. Overall score: 38.7%, a new all-time high.

---

## The checkpointer was empty every request, and the earlier msgpack fix was a no-op the whole time

Asked to check on the LangGraph phase's partial items, tracing Checkpointing found a real bug — and revealed an earlier fix this session had never actually done anything.

`GraphManager._config()` (`packages/graph/manager.py`) has always correctly passed `configurable.thread_id = str(state["thread_id"])` on every call — that part was fine, contradicting an old doc claim that thread IDs "weren't wired." The actual problem: `GraphBuilder.__init__` (`packages/graph/builder.py`) constructed a fresh `MemorySaver()` every time it ran, and both `builder` and `manager` are DI-wired as `providers.Factory` — so every single HTTP request got a brand-new, empty checkpoint store. LangGraph-level checkpointing provided zero benefit across turns; conversation continuity worked anyway, but only via `ConversationContextBuilder` reloading message history from the database, never via the checkpointer itself.

Fixed by pulling the checkpointer construction out of `GraphBuilder` entirely and wiring it as its own `providers.Singleton` in `packages/infrastructure/container/graph.py`, injected into `GraphBuilder` as a constructor parameter. This is safe in a way the earlier `Singleton`-caused memory bug wasn't: `MemorySaver` holds no per-request DB session, just an in-memory dict keyed by thread ID — nothing here can go stale the way a cached DB session did.

**Fixing this then exposed that this session's earlier msgpack-allowlist fix had been inert from the start.** `JsonPlusSerializer().with_msgpack_allowlist([...])` looks like it restricts what's allowed to deserialize, but its own source early-returns `self` unchanged whenever the base serializer's `_allowed_msgpack_modules` is already `True` or `False` — and `JsonPlusSerializer()`'s default is `True` ("allow everything, just warn"). So the original fix had never actually restricted anything, in either its first landing or since. It went unnoticed because the checkpointer was never actually reused across calls (see above) — no checkpoint was ever really deserialized, so neither the no-op allowlist nor its gaps had ever been exercised. The earlier "verified live: zero warnings across two turns" claim was a false negative, not a real fix.

Corrected by passing `allowed_msgpack_modules` directly at `JsonPlusSerializer(...)` construction, which does work. Since the allowlist is now genuinely restrictive rather than permissive, it also needed to be complete: auditing every custom type reachable from `GraphState` surfaced two more that weren't registered — `SearchResult` (`packages/knowledge/schemas.py`) and `Citation` (`packages/rag/schemas.py`) from the RAG fields, and `MemoryFact`/`MemoryType` (`packages/memory/schemas.py`) from `state["memories"]` — both of which started **hard-blocking** deserialization (not just warning) the moment the allowlist became real.

**Verified live:** a real 3-turn same-conversation test — told "remember the number 42," asked to recall it, asked to do arithmetic on it via the calculator tool — zero warnings, zero blocked deserializations, correct recall and correct math throughout. Direct DI inspection confirmed two independently-resolved `GraphBuilder` instances now share the exact same checkpointer object, while still being independently-constructed `Factory` instances otherwise. Checkpointing and Thread IDs both move from Partial to Done. LangGraph (Phase 5) moves from 33.3% to 44.4%; Session Management (Phase 6) moves from 25.0% to 50.0%. Overall score: 40.3%, a new all-time high.

---

## Reducers and Streaming — asked directly why both were still Partial/Pending, and both are now genuinely Done

Asked point-blank why Reducers and Streaming hadn't moved. Traced both to their real, current state in the code (not just re-reading the doc) and fixed them for real.

**Reducers.** `GraphState` had exactly one field with a real reducer — `messages`, via the built-in `add_messages`. Every other field (`search_results`, `context`, `citations`, `tool_calls`, `tool_results`, `memories`, etc.) just overwrites on each node write, which is fine only because nothing currently needs cross-step accumulation on those specific fields. Found a genuine case that did: `usage` (LLM token counts) was never even populated in `GraphState`, despite `ChatResponse.usage` already carrying real `response.usage_metadata` on every call (`packages/chat/chat_service.py`) — and a single turn can invoke the LLM node twice (once before a tool call, once after processing the tool's result), so simply overwriting would silently lose the first call's token count.

Added `merge_usage()` (`packages/graph/state.py`) — a real custom reducer that sums the numeric fields (`input_tokens`, `output_tokens`, `total_tokens`) while safely falling back to the latest value for non-numeric sub-fields, since LangChain's `UsageMetadata` also carries nested dict fields like `input_token_details` that can't be summed directly. Declared `usage: Annotated[dict[str, Any], merge_usage]`. `LLMNode` now returns just its own call's usage delta each time it runs, letting the reducer accumulate rather than pre-merging manually inside the node.

**Streaming.** `GraphManager.stream()` (`packages/graph/manager.py`) was real, working code that nothing ever called. The `stream` field was accepted at the API schema layer, threaded into `ChatRequest`, and then hardcoded to `False` right before it reached `GraphState` (`packages/application/services/chat_service.py`) — and the router only ever returned a single `ApiResponse[ChatResponseSchema]` JSON blob, with no `StreamingResponse` path to send chunks through even if the graph had streamed.

Built genuinely, end to end, across five files:
- **`packages/graph/nodes/llm.py`** — `LLMNode` now branches on `state["stream"]`. When true, it calls `ChatService.astream()` and pushes each token chunk through LangGraph's `get_stream_writer()` as it arrives (`{"type": "token", "content": ...}`), while still assembling the exact same final `AIMessage` the non-streaming path produces — the rest of the node's logic (usage tracking, message persistence) doesn't need to know the difference.
- **`packages/chat/chat_service.py`** — fixed a real bug found along the way: `ChatService.astream()` called `self._llm.astream(...)` directly, bypassing tool binding entirely (unlike `chat()`/`chat_sync()`, which correctly call `self._model(request)` first). Fixed to match.
- **`packages/graph/manager.py`** — `GraphManager.stream()` now passes `stream_mode="custom"` to `graph.astream()`, since the default `"updates"` mode only yields once per whole node completion, not per token — it would never have surfaced the writer's events otherwise.
- **`packages/application/services/chat_service.py`** — the application-layer `ChatService` gained a real `stream()` method: same conversation lookup and user-message save as `chat()`, but yielding tokens as `GraphManager.stream()` produces them, then persisting the fully-assembled response as one assistant message once the stream completes (refactored the state-building logic in `_execute_runtime()` into a shared `_build_state()` so both paths build identical `GraphState`, differing only in the `stream` flag).
- **`packages/api/routers/chat.py`** — the router now branches on `payload.stream`: `true` returns a genuine `StreamingResponse` (`media_type="text/event-stream"`), formatting each token as an SSE `data: {...}` line and a terminal `done` event; `false` keeps the existing single-JSON-response behavior unchanged.

**Verified live, both:**
- **Usage reducer** — a real tool-calling turn (2 LLM invocations in one turn) returned a combined, non-trivial `usage` dict via direct graph inspection; the merge function itself independently unit-verified for summing, `None`-handling on either side, and non-numeric fallback (`input_token_details`).
- **Streaming** — a real SSE HTTP request returned multiple progressive `token` events followed by a `done` event; the assembled text was confirmed, via direct database query, to match exactly one correctly-persisted assistant message — no duplication, no data loss. Tool-calling and cross-turn memory recall both still work correctly over the streaming path (verified with real calculator invocations and cross-turn number recall mid-stream conversation).

Full import sweep re-run clean (390 OK, same 14 pre-existing unrelated failures). LangGraph (Phase 5) moves from 44.4% to 66.7% — zero Partial items left in the phase, only Interrupt/Resume/Runtime Events remain Pending. Overall score: 42.0%, a new all-time high.

---

## `packages/knowledge/` becomes the canonical RAG implementation — this project crosses 50%

Asked "what's the issue with Document Processing," a live audit found the pipeline worked for `.txt` but nothing else was verified, two of four documented loaders crashed outright on a missing `unstructured` dependency, HTML support didn't exist, and there was no tenant isolation anywhere. Started fixing `packages/rag/` (the simpler, already-working stack) — installed `unstructured`/`docx2txt`, added the HTML loader, added a real cleaning step.

Mid-fix, by explicit request: **`packages/knowledge/` — not `packages/rag/` — should be the one true implementation.** `packages/knowledge/` is a second, much more ambitious ~70-file implementation (broader format support, a tenant-aware vectorstore design) that had sat alongside `packages/rag/` all session, documented as unwired and broken. The first attempt at this switch went too far — deleting most of `packages/knowledge/`'s files to replace them with a simplified rewrite — and was correctly stopped and reverted (`git checkout --` restored everything cleanly, since nothing had been committed). Redone properly: **fix every file in place, keep the existing structure, don't delete anything that wasn't asked for.**

**What was actually wrong, file by file** (none of this had ever successfully run):

- `loaders/base.py` — a stray, unindented `def __init__` sitting at module scope, completely outside the class it was clearly meant to belong to, meaning `BaseDocumentLoader` had no working constructor at all; its `execute()` method also referenced a bare `logger` that was never imported or defined anywhere in the file.
- 5 of 7 loader subclasses (`pdf.py`, `markdown.py`, `html.py`, `text.py`, `docx.py`) redundantly overrode `__init__` to require a `logger` argument with no default — but the factory always called `loader()` with zero arguments. Fixed by removing the redundant overrides (matching the two loaders, `csv.py`/`json.py`, that never had this bug).
- `json.py` called `self.handle_exception(...)`, a method that doesn't exist anywhere on `BaseDocumentLoader` — replaced with the real `DocumentReadError` pattern already used elsewhere.
- `splitters/base.py` defines `BaseSplitter`; `recursive.py`, `pipeline.py`, and `factory.py` all tried to import a nonexistent `DocumentSplitter` — the exact `ImportError` already flagged in earlier audit passes as a known, unfixed bug. Also simplified `BaseSplitter`'s abstract contract from an unused `SplitRequest`/`DocumentChunk`-based signature (referenced nowhere else in the codebase) to match what its one real implementation actually does: `list[Document] -> list[Document]`.
- `embeddings/factory.py` read `settings.embedding.provider`, but `EmbeddingSettings` only defines `default_provider` — another already-flagged, unfixed bug. Fixed — and then found something the earlier audits missed: `settings.embedding.model` defaults via alias to `LLM_MODEL` (the *chat* model's env var), not a real embedding model name, so real API calls 404'd (`models/gemini-3.1-flash-lite is not found... for embedContent`). Switched to `settings.rag.embedding_model` (`EMBEDDING_MODEL`, already proven correct in `packages/rag/`). Also added the missing `embed_query()`/`client` methods needed for search at all (the class only had batch `embed(chunks)`), and fixed a wrong OpenAI settings path (`settings.openai.api_key`, which doesn't exist, → `settings.ai.openai_api_key`) and an Ollama `base_url` reference to a nonexistent `settings.ollama`.
- Both vectorstore backends (`providers/chroma.py`, `providers/pgvector.py`) constructed `SearchResult(embedding=..., score=...)`, but the real schema has fields `chunk: DocumentChunk, score: float` — no `embedding` field exists. Fixed both to build a real `DocumentChunk` (fetching `documents` content from Chroma's query, which the code wasn't even requesting). Both also only implemented 4 of `BaseVectorStore`'s 9 abstract methods — `ChromaVectorStore()`/`PostgresVectorStore()` would have raised `TypeError: Can't instantiate abstract class` immediately. Added the missing `add`/`add_many`/`delete_chunk`/`delete_document`/`clear` to both.
- A systemic bug across `retrievers/manager.py`, `retrievers/base.py`, `retrievers/providers/{similarity,mmr,hybrid}.py`, and `KnowledgeManager.search()` itself: all of them typed their request parameter as `IngestionRequest` — a *file-ingestion* schema (`tenant_id`, `model_profile_id`, `file: Path`, `document_name`) — when they actually meant "a search request carrying a pre-computed query embedding." Added a real `RetrievalRequest` dataclass and fixed all five call sites. `KnowledgeManager.manager.py` also had a duplicate, shadowed `IngestionRequest` import (two different modules, same class name, second one silently wins) — confirmed as the root cause of an earlier-documented crash.
- `IngestionPipeline` called `.transform()` (real method: `.process()`), `.split(tenant_id=, content=)` (real signature takes `list[Document]`), and `.embed_documents(chunks=, tenant_id=, model_profile_id=)` (doesn't exist) — none of its three main collaborators matched what it actually called. Rewritten to use the real, now-fixed contracts, and simplified to persist through the vector store directly rather than separate Postgres `documents`/`document_chunks` rows (that would require a KnowledgeBase + File subsystem that doesn't exist yet — an explicit, unchanged scope boundary, not a new gap). `ingest()`'s return type changed from a `Document` ORM row (unbuildable — `Document` requires a `knowledge_base_id` and `file_id` FK to subsystems that don't exist) to the already-defined-but-unused `IngestionResponse` dataclass.
- A ChromaDB version-compatibility bug found only once search was finally reachable: this Chroma version requires multi-key `where` filters to be wrapped in an explicit `$and`, rejecting the implicit multi-key dict the code built (`ValueError: Expected where to have exactly one operator`). Fixed.

**A genuine bonus, found by accident:** tenant isolation had been explicitly deferred as "later" work earlier this session — but fixing the `where`-clause bug to make search work *at all* also activated the `tenant_id`/`model_profile_id` filtering that was already designed into `SearchFilter`. Verified live: identical search, two different tenants, correct chunk for one and zero results for the other.

**Wired for real** into the live chat path: `packages/infrastructure/container/rag.py` rebuilt to construct the full `packages.knowledge` stack via DI (loader → cleaner → splitter → embeddings → real `chromadb.PersistentClient`-backed `ChromaVectorStore` → `KnowledgeManager`); `packages/graph/nodes/retrieve.py` now calls `KnowledgeManager.search()` instead of the old `RetrievalPipeline`; `packages/graph/state.py`'s `Citation` import moved to `packages.knowledge.schemas` (added there); the memory pipeline's `EmbeddingManager` dependency (`postgres_store.py`, `pgvector_retriever.py`) now points at `packages.knowledge.embeddings.manager` — a compatible drop-in, since both expose the same `.client.aembed_query()` interface. Removed the now-dead `get_rag_manager` FastAPI dependency (zero callers, confirmed earlier this session) rather than leave it referencing a provider that no longer exists. `packages/rag/` itself was left untouched — still present, just no longer reachable from the live graph.

**Verified live, full pipeline, through the real DI-wired app:** a real `.txt` document ingested via `container.rag.knowledge_manager()`, then a real chat request correctly retrieved and cited its exact content ("the payload capacity of Unit-7 is 40 kilograms") — not a paraphrase, the precise figure from the source document. Full regression re-run and still passing: normal chat, cross-turn memory recall, and tool-calling (`847 * 293 = 248,171`, confirmed correct). Full import sweep: 393 OK, same pre-existing failures, three fewer than before (`packages.knowledge.splitters.{factory,pipeline,recursive}` no longer fail).

Document Processing (Phase 8) moves from 0.0% to 60.0% — all 5 roadmap-named formats plus JSON/CSV verified loading real content, real cleaning, real chunking, real multi-provider embeddings. Production Retrieval (Phase 9) gains Metadata Filtering, moving from 23.1% to 30.8%. **Overall score: 50.4% — this project crosses the halfway mark of its own roadmap for the first time.**

---

## Real IAM: `packages/sdk/iam/` wired for the first time, with working RBAC

Asked to implement IAM using the existing `packages/sdk/iam/` client SDK ("all endpoints are already included"). It's a real, mostly-complete HTTP client for an external IAM microservice — `IAMClient.auth`/`.users`/`.tenants`, with Pydantic models (`CurrentUser`, `Role`, `Permission`) already carrying roles/permissions. It had never once been exercised: `packages/sdk/iam/{auth,user,tennets}.py` all built their `BaseClient` with `base_url=str(settings.url)`, but the real field on `IAMSettings` is `base_url` — confirmed live, `AttributeError` before the fix. Fixed in all three files.

**Two decisions made explicitly with the user before writing any code**, since no real IAM backend is reachable in this environment (`IAM_BASE_URL=http://localhost:3000/...` refuses connections; `.env`'s `client_secret`/`introspection_api_key` are placeholder values):

1. **Auth strategy: per-request `IAMClient.auth.get_current_user()`** with the incoming Bearer token, not local JWT/JWKS signature verification. Uses only what's already coded in the SDK, zero new dependencies. The SDK does define a JWKS endpoint "for local RS256 JWT verification," but nothing parses a JWT anywhere in the codebase — building that out was explicitly deferred, so it stays a documented, unused endpoint constant, same as before.
2. **Fail open.** Missing token, invalid token, or an unreachable IAM service — the request proceeds with the existing default-tenant/default-user fallback (logged loudly), not a 401. Real permission enforcement only activates once a token is actually, successfully verified. This keeps the entire regression suite built all session (calling the API with no auth headers) working unchanged, and matches the reality of a not-yet-deployed backend, without pretending to enforce security that isn't actually backed by anything reachable yet.

**Built:**
- **`packages/auth/service.py`** (new — the first real code in a package that had been an empty `# init` all session): `AuthService.resolve(access_token)` — `None` if there's no token; on `SDKException` or `httpx.HTTPError` (covers both "IAM rejected the token" and "IAM is unreachable"), logs a warning and returns `None` rather than raising. Only a genuinely successful IAM response returns a real `CurrentUser`.
- **`packages/infrastructure/container/iam.py`** (new): the shared `httpx.AsyncClient` → `IAMClient` → `AuthService` chain, composed into `ApplicationContainer` as `iam`. This is the **first `packages/sdk/*` client ever wired into DI** — Upload and Notification remain equally unwired, no precedent existed before this.
- Fixing this surfaced a second, unrelated bug in `packages/infrastructure/http/client.py`'s `create_http_client()` (itself dead code until now, never called by anything): `http2=True` with the `h2` package not installed — `ImportError`, confirmed live, fixed by dropping `http2=True` rather than adding a new dependency for a non-essential feature.
- **`packages/api/middleware/authentication.py`** (rewritten from a 1-line stub): a real `AuthenticationMiddleware` reading `Authorization: Bearer <token>`, resolving via `AuthService`, and setting `request.state.current_user`. On a real, verified user, it **overrides** `request.state.tenant_id`/`user_id` (set moments earlier by `TenantMiddleware`'s header-or-default fallback) with the authenticated identity. This uses `dependency_injector`'s `@inject`/`Provide[...]` pattern *inside a Starlette middleware*, not just a FastAPI route dependency — the first time that combination has been used anywhere in this codebase, and it needed a specific registration order to work: `AuthenticationMiddleware` is added *before* `TenantMiddleware` (Starlette executes in reverse-of-registration order — innermost/added-first runs last, right before the route), so Auth genuinely runs *after* Tenant and can override its default.
- **`packages/api/dependencies.py`**: added `get_current_user()` (reads `request.state.current_user`) and `require_permission(code)`/`require_role(code)` dependency factories — no-op (fail-open) when there's no verified user, `403` when a verified user lacks the required code. Existing routes (`chat.py`, `conversations.py`) were deliberately **not** retrofitted with specific required permissions — no permission taxonomy exists for them yet, and this pass delivers the reusable mechanism, not a new authorization policy guessed for two routes that were never designed with RBAC in mind.

**Verified live, against real infrastructure, not mocks:**
- `AuthService.resolve()` called against the actual configured (and genuinely unreachable) `localhost:3000` — confirmed it logs the warning and returns `None` rather than raising.
- A real chat request through the full app with a bogus `Authorization: Bearer totally-fake-token` header produced the exact expected log line (`"IAM auth failed, falling back to default identity", error="All connection attempts failed"`) and still completed correctly end to end — including a genuine tool-calling turn (`55 * 3 = 165`, correct) — proving the fail-open path doesn't disturb anything.
- `require_permission()`/`require_role()` unit-verified on all four branches directly: no `current_user` → passes silently; a real `CurrentUser` with the required code → passes; missing it → raises `403` with the expected detail message, for both permissions and roles.
- Full import sweep clean (395 OK, same pre-existing failures — two fewer than before, since `packages.sdk.iam.*` submodules now import cleanly too).

IAM (Phase 2) moves from 28.6% to 71.4% — User Context, RBAC, and Permission Validation move from Pending to Done; JWT Validation moves to Partial (genuinely validated, just via IAM delegation rather than local signature verification); Refresh Token Validation is the one item still Pending. **Overall score: 52.9%, a new all-time high.**

---

## Document Processing (Phase 8) completed — the second full phase this project has ever had

Asked to complete Document Processing. Six items were Partial/Pending: Metadata Extraction, Markdown-aware chunking, Semantic chunking, Async indexing, Incremental indexing, Batch indexing. Two decisions made explicitly with the user before building, since the remaining work required real architectural choices, not just bug fixes:

1. **Async indexing uses FastAPI `BackgroundTasks`**, not the already-installed-but-fully-dead `arq` dependency — zero new infrastructure, satisfies "off the request path." Wiring `arq` for real is Phase 12 (Background Jobs) territory, not this pass.
2. **Build a real document persistence layer + `POST /api/v1/documents` route.** Without it, Incremental Indexing has no way to detect a repeat upload at all, and none of this phase's work would be provable through the running app — the same "verified live, not just in Python" bar every fix this session has been held to.

**Two more real, never-exercised repository bugs found along the way** (same "written, never run" pattern as `packages/knowledge/` and `packages/sdk/iam/` earlier this session — nothing had ever called either method before):
- `DocumentRepository.get_by_filename` filtered `Document.filename` — the real column is `file_name`.
- `KnowledgeBaseRepository.list_enabled` filtered `KnowledgeBase.enabled` — the real column is `status` (a `KnowledgeBaseStatus` enum). Also added a tenant-scoped `get_by_tenant_and_name`, since the existing `get_by_name` wasn't scoped to `tenant_id` at all — a cross-tenant leak nothing had hit yet, since nothing had ever called it either.

Both fixed. A new `packages/knowledge/bootstrap.py` adds `ensure_default_knowledge_base()`, mirroring the existing get-or-create idiom in `packages/conversation/bootstrap.py` exactly — nothing in the app had ever created a `KnowledgeBase` row before this.

**Design decision: the vector store stays the retrieval source of truth.** The new `Document` row is bookkeeping for identity/checksum/status only — chunk content keeps flowing into Chroma exactly as it did before. This kept the diff focused on what was actually missing instead of restructuring the already-working, already-proven search path.

**Metadata Extraction.** PDF already surfaced `author`/`page` natively via `PyPDFLoader` (confirmed live) — no code needed there. DOCX did not (`Docx2txtLoader` only extracts text), so `DocxDocumentLoader` now separately reads `python-docx`'s `core_properties` for `author`/`title`. Real `token_count` via `tiktoken` (`cl100k_base`) replaces the previous hardcoded `0`. Chunks now carry `page_number` and `section` metadata pulled from loader/splitter output. Every document gets a real `ingested_at` timestamp.

**Markdown-aware chunking.** `packages/knowledge/splitters/markdown.py` (previously an empty stub) now has `MarkdownDocumentSplitter` — a two-stage split using `langchain_text_splitters.MarkdownHeaderTextSplitter` (already installed, no new dependency) for header-aware splitting, then a `RecursiveCharacterTextSplitter` pass within each section to cap size. Verified live: real `#`/`##` heading text correctly attached as `h1`/`h2` chunk metadata on genuinely multi-section markdown.

**Semantic chunking.** New `packages/knowledge/splitters/semantic.py`, `SemanticDocumentSplitter` — hand-rolled rather than pulling in `langchain_experimental.SemanticChunker` (not installed, and not worth adding for a fairly small algorithm, given that package's history of breaking changes). Sentences are split via a simple regex, embedded in one real batch call, and consecutive-sentence cosine distances (pure Python, no numpy dependency assumed) determine breakpoints at the 95th percentile (`statistics.quantiles`). Oversized resulting chunks are capped by a recursive fallback. **Verified live on genuinely mixed-topic text** — a paragraph about Ferrolabs robotics followed by a pasta carbonara recipe — and it split exactly at the topic boundary, not at an arbitrary size cutoff. A 2-sentence edge case was also checked to confirm it doesn't crash `statistics.quantiles` on too little data.

**A real selector, not just three classes sitting unused.** `packages/knowledge/splitters/factory.py` (previously a single-class wrapper around the recursive splitter only) is now `SplitterFactory`, choosing between all three strategies. `IngestionRequest` gained `chunking_strategy: Literal["auto", "recursive", "markdown", "semantic"] = "auto"` — under `"auto"`, `.md`/`.markdown` files get the markdown splitter and everything else gets recursive; explicit values force a specific strategy regardless of file type. Semantic chunking stays opt-in rather than a silent default, since it's meaningfully more expensive (embeds every sentence).

**Batch indexing was a real bug, not just an inefficiency.** `IngestionPipeline._embed()` called `embed_query()` once per chunk in a loop. Replaced with a single real `aembed_documents()` batch call. **Verified live via a call-count check**, not just "it still works": a 20-chunk document produced exactly 1 embedding API call, not 20 — confirmed by patching `GoogleGenerativeAIEmbeddings.aembed_documents` at the class level and counting invocations.

**Incremental indexing, proven live, not asserted.** `ingest()` now computes a real SHA-256 checksum of the uploaded file's bytes before doing any work, and checks it against existing `Document` rows scoped to the knowledge base via the new `get_by_checksum`. If found, it returns immediately with `skipped=True` and zero new chunks/embeddings — no re-load, no re-embed, no re-store. **Verified live with two real HTTP uploads of identical content**: the second call returned `skipped=True`, `chunk_count=0`, and reused the exact same `document_id` as the first — not a duplicate row.

**Async indexing.** `packages/api/routers/documents.py` (previously a 1-line stub) now defines a real `POST /api/v1/documents` — accepts a multipart upload, resolves the tenant's default `KnowledgeBase` and `ModelProfile`, saves the file to `settings.storage.upload_directory`, and schedules ingestion via `background_tasks.add_task(...)`, returning `202 Accepted` before any embedding work starts. The background task deliberately does **not** reuse the original request's database session — it opens its own fresh `request_scoped_session(container)`, the same pattern already used by `get_conversation_manager` in `packages/api/dependencies.py` — since a background task runs after the response is sent, by which point the original request-scoped session may already be closed. Along the way, found FastAPI's file-upload support requires `python-multipart`, which wasn't installed — installed it (a genuinely missing dependency, not a version pin issue).

**A DI-lifetime detail worth calling out explicitly, given this session's history with exactly this bug class:** `ingestion_pipeline` and `knowledge_manager` (`packages/infrastructure/container/rag.py`) now depend on `repositories.document`, which is itself `Factory`-wired onto a per-request database session. Both providers were changed from `providers.Singleton` to `providers.Factory` in the same pass — getting this wrong would have silently orphaned every `Document` status update into a session nothing ever commits, the exact bug fixed earlier this session for the memory pipeline.

**Verified live, full pipeline, through the real running app — not direct Python calls:**
- A real multipart upload → `202 Accepted` immediately → background task correctly flips `Document.status` `PENDING → PROCESSING → READY`.
- A real chat request afterward correctly retrieved and cited the uploaded content by exact figures ("the maximum payload capacity of 88 kilograms and a battery life of 14 hours") — not a paraphrase, the precise numbers from the source.
- Full existing regression suite re-run and still passing: cross-conversation memory recall (Rust/Ferrolabs), tool-calling (`847 * 293 = 248,171`), and real SSE streaming.
- Full import sweep clean (397 OK, same 11 pre-existing failures).

Document Processing (Phase 8) moves from 60.0% to **100%** — the second full phase this project has ever completed, after Memory (Phase 7). The new Upload API also moves APIs (Phase 14) from 14.3% to 28.6% (the roadmap's Upload API and Documents API are two separate, differently-scoped items — only the narrower, create-only Upload API is Done; Documents API still needs list/fetch/delete). **Overall score: 58.8%, a new all-time high.**

---

## Production Retrieval (Phase 9) completed — the roadmap's own ⭐ centerpiece, the third full phase this project has ever had

Asked to implement Phase 9 in full after a status check. 4/13 items were already Done (Query Embedding, Dense Retrieval, Similarity Search, Metadata Filtering), 1 Partial (Context Building), 8 Pending (Query Classification, Query Rewriting, Query Expansion, Hybrid Search, BM25, Re-ranking, Prompt Construction, Citation Generation). Two real architectural decisions confirmed with the user before building:

1. **Hybrid/BM25 search: build it now**, using `rank_bm25` (small, pure-Python, no model download) over an in-memory candidate pool fetched from the vector store per search, fused with dense results via reciprocal rank fusion (RRF, `k=60`). Accepted trade-off: the BM25 index rebuilds from scratch on every search call — fine at current data scale, would need a persisted/incremental index at real production scale.
2. **Re-ranking: a real cross-encoder** (`sentence-transformers`' `cross-encoder/ms-marco-MiniLM-L-6-v2`), not a lightweight heuristic — `sentence-transformers` was already an installed dependency, Hugging Face Hub confirmed reachable. Accepted trade-off: a one-time ~90MB model download on first use (mitigated by lazy-loading — the DI singleton constructs instantly, the actual model only loads inside the first real `rerank()` call), plus real per-call latency on every retrieval-routed turn.

**Query Classification, Rewriting, Expansion.** New `packages/planner/query_analyzer.py`'s `QueryAnalyzer` — one `LLMManager.with_structured_output(QueryAnalysis)` call per turn, deciding `needs_retrieval`, rewriting the query to resolve pronouns/context, and generating up to 3 expansion variants. `GraphPlanner` (`packages/planner/planner.py`) now calls it, failing open to the original `RETRIEVAL_KEYWORDS` substring check on any LLM error — a classifier hiccup should never crash a turn. `GraphState` gained `rewritten_query: str | None` and `expanded_queries: list[str]`.

**Hybrid Search / BM25.** `packages/knowledge/retrievers/providers/hybrid.py`'s `HybridRetriever` went from `raise NotImplementedError("Hybrid retrieval is not implemented.")` to real dense+BM25 fusion: the vector leg reuses `similarity_search()`, the keyword leg fetches a bounded candidate pool via a new `list_chunks()` method and scores it with `rank_bm25.BM25Okapi`, and both ranked lists are merged via RRF, deduped by chunk id. `RetrieverFactory` (`packages/knowledge/retrievers/factory.py`) — confirmed dead code, the DI container hardcoded a `SimilarityRetriever` singleton and never called it — is now genuinely wired in `packages/infrastructure/container/rag.py`, strategy-selected via a new `settings.rag.retrieval_strategy` setting (default `"hybrid"`).

**`list_chunks` on both vector store backends.** New abstract method on `BaseVectorStore`, implemented in `ChromaVectorStore` (via `collection.get(where=..., limit=...)`) and `PostgresVectorStore` (via a bounded `select(Embedding)...limit(...)` query) — both must implement every abstract method to stay instantiable. Also added a thin pass-through on `VectorStoreManager`.

**Re-ranking.** New `packages/knowledge/reranking/cross_encoder.py`'s `CrossEncoderReranker` — lazy-loads the underlying `sentence_transformers.CrossEncoder` model on first real `rerank()` call, not in `__init__`, so wiring it as a DI singleton at container-build time never triggers the download. `rerank(query, results, top_k)` builds `(query, chunk.content)` pairs and calls `.predict()` via `asyncio.to_thread(...)`, since it's synchronous/CPU-bound and would otherwise block the event loop.

**`RetrieveNode` rewritten as the real orchestration point.** `packages/graph/nodes/retrieve.py` now: uses `state.get("rewritten_query")` as the primary query (falling back to the raw last message), searches it plus every `expanded_queries` entry, merges results deduped by chunk id (keeping the best score per chunk), reranks the merged candidates via `CrossEncoderReranker`, and populates `state["context"]`, `state["search_results"]` (mapped from the nested-`chunk` vectorstore `SearchResult` shape to the flat `packages.knowledge.schemas.SearchResult` shape `GraphState` declares), and `state["citations"]`.

**Context Building.** `PromptBuilder` (`packages/prompts/builder.py`) gained a `_dedup_and_budget()` step — drops exact-duplicate chunks (multi-query retrieval can easily surface the same chunk twice), then truncates to a token budget via the already-established `tiktoken.get_encoding("cl100k_base")` pattern from `packages/knowledge/pipelines/ingestion.py` (new `settings.rag.context_token_budget`, default 4000).

**Prompt Construction — credited as Done, no code change.** `PromptBuilder` already combined context + memories + conversation history + the user's question into the final prompt via a real `ChatPromptTemplate` (built and verified earlier this session under Phase 4/LangChain) — it satisfied this item's definition exactly but had never been credited under Phase 9 until this pass.

**Citation Generation.** `ChatService._execute_runtime()` (`packages/application/services/chat_service.py`) now returns `(text, citations)` instead of just text, mapping `state["citations"]` into new `CitationDTO`s. `ChatResponse` DTO and `ChatResponseSchema` both gained a `citations` field; new `CitationSchema` in `packages/api/schemas/chat.py`; `packages/api/routers/chat.py` maps through. **Deliberately not persisted to `MessageCitation`** (a real, migrated DB model with zero write paths) — its `chunk_id` FKs to a real `document_chunks` Postgres row, but Document Processing (Phase 8) deliberately decided chunk content stays in the vector store only; populating it would mean reopening that decision. **Deliberately not threaded through SSE streaming** (`ChatService.stream()`) — would need a second event type to carry citations, and the roadmap doesn't require it. Both are documented, explicit gaps.

**Verified at every level, not just "the code exists":**
- Unit-level: a constructed case proved RRF fusion surfaces an exact-match chunk (`SKU-9000X`) that dense-only search's top-3 never included at all. A constructed case proved the cross-encoder correctly promotes the genuinely relevant chunk from last place (lowest of three initial scores) to rank 1.
- Full DI container instantiation: `c.rag.retriever_manager()` resolves to a real `HybridRetriever`, `c.rag.reranker()` to a real `CrossEncoderReranker`, `c.graph.planner()` to a `GraphPlanner` holding a real `QueryAnalyzer` instance.
- Live, through the running app: a real `.txt` document with two distinct product codes (`ZBR-9410`, `FLX-77Q2`) ingested via `POST /api/v1/documents`. `"What is the payload capacity of the ZBR-9410?"` → correct answer (63kg) with a real citation pointing at the actual ingested chunk. The pronoun follow-up `"what about its battery life?"` (zero explicit context) → correctly resolved to the same product, correct answer (11 hours) — proof query rewriting, not just classification, actually works. `"Thanks, that is helpful!"` → correctly zero citations (retrieval genuinely skipped, not just empty results). Streaming (`stream: true`) still works, correctly retrieving the *different* `FLX-77Q2` chunk for a different query in the same conversation. A weather tool-calling request still worked unchanged, confirming retrieval-routing changes didn't regress tool routing.
- Full import sweep clean across every touched module. No new errors or tracebacks in the server log across the full test session.

Production Retrieval (Phase 9) moves from 30.8% to **100%** — the third full phase this project has ever completed, after Memory (Phase 7) and Document Processing (Phase 8). **Overall score: 66.4%, a new all-time high.**

---

## Removed the legacy `packages/rag/` and `packages/agent/` packages

Asked to remove unnecessary RAG file/folders. Traced `packages/rag/` — the entire pre-`packages/knowledge/` RAG implementation (19 files: `manager.py`, `pipeline.py`, `retriever.py`, `indexer.py`, `loader.py`, `splitter.py`, `embeddings.py`, `vectorstore.py`, plus `builders/`/`pipelines/` subpackages) — and found exactly one reference to it anywhere outside itself: `packages/agent/context.py` importing `Citation`/`Context` from `packages.rag.schemas`. Tracing further, `packages/agent/` (`context.py`, `prompt.py`, `response.py`, `runtime.py`) was itself dead: `packages/infrastructure/container/application.py` constructed `prompt_builder`/`agent_runtime` DI providers from it, but nothing downstream — no router, no service — ever consumed either provider. Deleted both packages together via `git rm`, and removed the now-dead imports and provider wiring from `application.py`.

**Verified, not just assumed safe:** full DI container construction still succeeds end to end (`ApplicationContainer().init_resources()`, `chat_service.chat_service()`, `rag.retriever_manager()` all still resolve correctly); a full `packages/` import sweep shows the identical pre-existing failure set as before (403/426 OK, down from 428/451 — the 25-file drop matches the two deleted packages exactly, zero new failures); a live `POST /api/v1/chat` request against the running server still returns `200` with a correct response. `docs/UNUSED_FILES.md` updated to mark the deletion and correct several other entries that had gone stale relative to `packages/knowledge/`'s current live status.

---

## `graph.png` rendering — the misleading "could not render" warning fixed for real

Asked to regenerate the graph visualization. Every startup logged `Could not render graph.png: UnicodeEncodeError(...)`, implying rendering failed — it didn't. `packages/graph/visualizer.py`'s `GraphVisualizer.save_png()` writes the PNG to disk first, then `print()`s a `✅ Graph saved as {filename}` success message; the emoji can't be encoded by Windows' console codepage, so the `print()` itself throws, and `lifespan.py`'s broad `except Exception` logs it as a render failure even though the file was already written correctly one line earlier. Removed the emoji. Confirmed live: `graph.png` regenerates cleanly with zero exceptions, and the graph itself is unchanged in shape (`planner → load_memory → retrieve → llm ⇄ tool → extract_memory`) — this session's Production Retrieval work made the nodes' internals real, not the graph topology.

---

## The knowledge-base hallucination — same bug class as the earlier memory fix, this time for RAG

The user pasted a live transcript: asked "do you have any knowledge base," the app confidently denied having one, describing RAG as session-only ("paste a document into this chat... once you close the session, that information is gone") — false, given Document Processing and Production Retrieval are both 100% done this session. Root cause: `packages/conversation/bootstrap.py`'s `ensure_default_agent()` — the actual, live `Agent.system_prompt` fetched into `GraphState` on every request (`packages/prompts/system.py`'s `get_base_system_prompt()` is dead code, imported but never called anywhere, confirmed via grep) — explicitly described the persistent long-term memory system (fixed earlier this session) but said **nothing at all** about document upload or retrieval capability. With no instruction telling it otherwise, the model fell back to its training-data default of denying persistent RAG. Confirmed via direct DB query: all 45 provisioned `agents` rows carried the memory-only prompt.

Fixed by extending the prompt with an explicit knowledge-base capability section (upload → chunk → embed → persist, hybrid search + re-ranking retrieval, citations back to source) and the same "do not default to generic claims of statelessness" instruction already used for memory. Since `ensure_default_agent()` only runs its seed path for brand-new tenants (`get_by_tenant_and_name` returns existing rows unchanged), also ran a direct `UPDATE agents SET system_prompt = ...` for all 45 already-provisioned rows — the same pattern used for the memory-prompt fix earlier this session. **Verified live, same tenant/conversation that produced the wrong answer**: `"Do you have any knowledge base?"` now correctly describes real document upload, hybrid retrieval, and citations, and correctly mentions long-term memory too.

---

## Two more real bugs, found reproducing a second reported hallucination

The user pasted a second live transcript: asked about a specific ("Ferrolabs Unit-9") product, the app claimed it had "conducted a thorough search," found nothing in "public records"/"public databases," and suggested pasting a manual into the chat so it could "use my RAG capability" — directly contradicting the knowledge-base fix above (RAG isn't session-paste-only) and framing an internal KB miss as a failed public web search. Reproducing it live surfaced two distinct, real bugs, not a stale-server issue:

1. **`PromptBuilder` attributed retrieved content to the user, not the retrieval system.** Long-term-memory facts and RAG context were both injected as separate `"human"`-role messages ahead of the real user turn — with no attribution, the model read them as things the *user* had just typed. Reproducing the exact reported query got back `"It appears you have provided some information regarding Ferrolabs Robotics products..."` — confirming the bug directly rather than guessing at it. Fixed by folding memory/context into the single system message instead, explicitly labeled `(not written by the user — this is retrieval output)`. Also added an explicit branch for the *attempted-but-empty* case (`state["context"] == []`, distinct from `None`/never-attempted): `"The knowledge base was searched for this specific question and no matching documents were found. ... do not invent a public/web search you did not perform."` — directly countering the "public records" hallucination.
2. **No relevance floor on reranked results.** `RetrieveNode` always kept the top `settings.rag.max_results` reranked candidates regardless of score — with a small candidate pool, "best of what's available" could still be a confidently irrelevant match (a made-up "Zorblax-Quantum9000 hyperdrive engine" query returned a citation with cross-encoder score `-7.1`, attached to an answer that admitted finding nothing relevant). Added `settings.rag.min_relevance_score` (default `0.0`) and filter reranked results below it before they reach context/citations.

**Verified live, both fixes together:** the exact reported query ("Ferrolabs Unit-9 Specification") now correctly says no such product exists but lists what the knowledge base *does* have (FLX-77Q2, ZBR-9410), with a real citation. A genuinely irrelevant query (fictional hyperdrive engine) now gets zero citations and a response that accurately describes searching the internal KB, not a fabricated public search. A genuinely relevant query (ZBR-9410 payload capacity) is unaffected — correct answer, real citation, unchanged score.

---

## The user still saw the old behavior after both fixes — root cause was poisoned conversation state, not remaining code, and it surfaced a real architectural gap

The user re-tested the identical query against their own long-running dev server and still got the old wrong answer, word-for-word ("as I mentioned previously... I do not have access to private company databases"). Re-testing the same query against fresh conversations (including on the exact same live server, via `curl` directly) confirmed the code fixes above genuinely work. The actual cause: the user's frontend always resumes one fixed conversation (`session_id: "test-session-1"`, tenant/user `12345678-...`), which had **117 messages accumulated since 2026-07-18** — three days of testing across many now-fixed bugs. The model was reading its own old, pre-fix wrong answers from that conversation's history and staying self-consistent with them (hence "as I mentioned previously"), regardless of how correct the underlying prompt logic now was.

**Deleted the 117 messages** from that conversation (user-approved via AskUserQuestion) so it starts clean going forward.

**A second, more serious layer was found investigating further: 63 stored long-term memory facts for that same tenant/user, and most were the model's own hallucinated self-descriptions captured as durable "facts"** — roughly 10 near-duplicate variants of `"The AI operates on a session-based memory model and does not retain information across chat sessions"`, plus at least two fully fabricated facts (`"Product code ZBR-9410 is associated with Zebra Technologies"` — invented; ZBR-9410 is the real Ferrolabs product this session ingested — and `"Ferrolab IV is a digital indicator for cast iron thermal analysis by Vesuvius"` — an invented brand). Since memory facts are recalled into *every* conversation for a user regardless of which conversation is used, these would have kept re-poisoning answers even in a brand-new conversation. **Deleted all 63 rows** for this tenant/user (user-approved).

**This points at a real, unaddressed architectural gap, not yet fixed:** nothing in the memory-extraction pipeline (`ExtractMemoryNode`/`LLMMemoryExtractor`) stops the model's own claims about its own capabilities from being captured as if they were facts about the world. A single wrong self-description, once extracted into long-term memory, becomes self-reinforcing — every later turn recalls it as ground truth and answers consistently with it, compounding the original mistake indefinitely. Flagged in `docs/BUILD_STATUS.md`'s priority list as a follow-up: fact extraction should exclude AI self-referential/meta claims, or at minimum weight them low enough to be overridden by the system prompt's actual capability description.

**Verified live, same conversation, same query, after cleanup:** correctly explains it searched and found nothing (this tenant genuinely has no ingested documents — the test document from earlier this session was uploaded under a *different* tenant), suggests checking internal documentation, and — critically — no longer claims to be stateless/session-based and no longer repeats the fabricated Zebra Technologies association.

---

## Added `docs/ARCHITECTURE_TUTORIAL.md` — a function-by-function tutorial of the whole live system

Asked for complete, tutorial-style documentation of the codebase. Scoped with the user first (single doc vs. many, lifecycle-driven vs. pure module reference) rather than guessing — landed on one large doc, organized around real request lifecycles rather than a flat file listing, since that's how the code actually executes.

Research was originally split across 5 parallel background agents (API layer, graph/planner/prompts, knowledge/RAG, memory/conversation/application, infrastructure/domain/IAM/tools); all 5 failed mid-run from hitting the session's API rate limit, not from any real problem with the task. Rather than retry the same approach, did the research directly instead — reading every relevant file with `Read`/`Grep`/`Glob` across roughly 60 files spanning API routers, middleware, the DI container tree, the LangGraph node chain, the memory subsystem's LCEL chains, tool implementations, the IAM SDK, and every domain model.

The result covers, function-by-function, in call order: the full `POST /api/v1/chat` request lifecycle (middleware → router → `ChatService` → `GraphManager` → all six graph nodes → `PromptBuilder` → response); document upload/ingestion (`IngestionPipeline`'s load→clean→split→embed→store, including the checksum-based skip logic); the hybrid retrieval + re-ranking pipeline (RRF fusion math, lazy cross-encoder loading, the relevance-floor filter); the memory load/extract/summarize cycle, including the LCEL chains and the exact gap that caused this session's hallucination-loop incident; SSE streaming, including the documented citations gap; and authentication/multi-tenancy's fail-open design end to end. A closing module reference, data model table, and configuration reference fill in anything not already covered by a lifecycle walkthrough, plus a dead-code map distinguishing what's live from what's confirmed unused (`packages/rag/`/`packages/agent/`'s removal, six unwired API routers, etc.).

Verified accuracy at the end by cross-checking one non-obvious claim (`GraphNodes`'s exact field names/types feeding `GraphBuilder`) directly against the file rather than trusting the write-up from memory — matched exactly.

---

## Four companion docs added — Quickstart, Extending, Testing Playbook, Deployment — plus four real bugs found and fixed writing the last one

Asked what else could round out the documentation. Presented four options with a recommendation; the user picked all four.

**`docs/QUICKSTART.md`** — hands-on curl walkthrough tracing one document through upload → citations → pronoun follow-up → empty-result honesty → cross-conversation memory recall → streaming → tool-calling. Attempted to re-verify live before writing it; blocked by Postgres being unreachable (`ConnectionRefusedError`) and Docker Desktop not running, so wrote it from this session's own extensively-verified real transcripts instead of fabricating new output — flagged that plainly in the doc rather than silently presenting it as freshly re-checked.

**`docs/EXTENDING.md`** — four contributor-facing walkthroughs (add a tool, add an LLM provider, add a document loader, wire a new DI service), each naming exact files and reusing the codebase's own existing patterns (`BaseProvider._create_model()`, `LoaderFactory`'s extension dict, `ToolManager.register()`) rather than a generic template. The DI section restates the `Singleton`-vs-`Factory` session-capture bug class explicitly, since it's the one mistake this exact kind of change has caused for real, more than once.

**`docs/TESTING_PLAYBOOK.md`** — a manual verification checklist (the closest thing to a test plan this project has, given zero pytest coverage) covering every subsystem, plus a full troubleshooting procedure for the poisoned-conversation/poisoned-memory hallucination-loop failure mode from two passes ago — written as a general diagnostic ("is it code or is it data, check in this order") rather than just a postmortem of the one incident.

**`docs/DEPLOYMENT.md`**, and four real bugs found while verifying it against the actual `docker/`, `docker-compose.*.yml`, and `Makefile` files rather than describing them from assumption:
1. `docker/Dockerfile`'s `HEALTHCHECK` pinged `http://localhost:8000/health` — the real route is `/api/v1/health` (the whole API is mounted under that prefix). Docker would have reported the container permanently unhealthy regardless of the app's real status. Fixed.
2. `docker/Dockerfile`'s final `CMD` was a JSON array split across multiple lines with no line-continuation backslashes — not valid Dockerfile syntax; each line was being parsed as its own bogus instruction (caught by the IDE's own Dockerfile linter mid-edit). Collapsed to one line. Applied the same stray-comment cleanup (`# Empty file` header on a file that very much wasn't) to `docker/Dockerfile.worker` and `docker-compose.prod.yml`.
3. `Makefile`'s `dev`/`prod` targets pointed at `docker/compose/docker-compose.{dev,prod}.yml` — a path that has never existed; the real files are at the repo root. Fixed the path. Doing so exposed that `docker-compose.dev.yml` is an empty placeholder (zero services) and `docker-compose.prod.yml` assumes a pre-built, already-tagged image rather than building from `docker/Dockerfile` — both documented honestly in `DEPLOYMENT.md` as not-yet-functional rather than silently worked around, since inventing real content for either is a product decision, not a doc-writing one.
4. `docker-compose.prod.yml`'s `env_file: ../../.env` assumed the file lived two directories deeper than its actual location (a leftover from when the Makefile still pointed at `docker/compose/`). Fixed to `.env`. Also added `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` to `.env.example` — the official `pgvector/pgvector` Postgres image requires them to self-initialize, and `docker-compose.yml`'s own healthcheck already referenced `${POSTGRES_USER}` with nothing in `.env.example` ever defining it.

All four new docs cross-linked from `docs/ARCHITECTURE_TUTORIAL.md`'s intro.

---

## Tools (Phase 10) completed — Knowledge Base Search and Document Search, the last two items, both implemented for real

Asked why these two remained pending given all the RAG work this project has done. Answer: Phase 9's retrieval is automatic and implicit (the planner decides per-turn, scoped to the tenant's one default KB); Phase 10's two items are meant to be explicit, model-invokable tools — the same shape as `calculator`/`get_weather` — that the assistant chooses to call mid-conversation against a specific KB or document. The underlying capability (`KnowledgeManager.search()`/`search_by_document()`) already existed and worked; nobody had wrapped either as a real tool. User said to build them.

**New `packages/tools/builtin/knowledge_base.py`** — `make_knowledge_base_search_tool()`/`make_document_search_tool()`, factories rather than the module-level `@tool` functions the other four tools use, since `KnowledgeManager` is itself `providers.Factory` (session-bound) — capturing one at import time would be the exact Singleton-captures-a-stale-session bug class this project has hit before (memory pipeline, ingestion pipeline). `tenant_id`/`model_profile_id` are never LLM-visible tool parameters — pulled from graph state at call time via LangGraph's `InjectedState` (`Annotated[dict, InjectedState]`), so the model can never specify or search outside its own tenant. Verified this composes correctly with a standalone test before wiring it into the real app: confirmed `tool.args` excludes `state` entirely from the LLM-visible schema, and confirmed (after an initial bare `ToolNode.ainvoke()` call failed with `Missing required config key` — it only works inside a compiled `StateGraph`, not called standalone) that a closure-captured dependency and injected state both come through correctly inside a real compiled graph.

**A real bug caught before it ever shipped, not found live:** wiring the second tool's dependency (`rag.knowledge_manager`, itself `Factory`) through `ToolsContainer` meant `manager` had to become `Factory` too — but `registry`/`executor` were still `Singleton`. Since `ToolManager.register()` mutates the registry's shared, name-keyed dict, two concurrent requests would have clobbered each other's `search_knowledge_base`/`search_document` closures (each bound to a *different* request's `KnowledgeManager`) — request A could end up executing against request B's database session. Caught by reasoning through the DI graph before testing, not by hitting the race in practice. Fixed by making `registry`/`executor` `Factory` too, so each request gets a fully isolated tool-registry triplet; the four stateless tools are cheap enough to reconstruct and re-register every request that this costs nothing meaningful. `packages/infrastructure/container/application.py`'s `tools` container construction also had to move to after `rag` in the file, since it now depends on `rag.knowledge_manager` and Python class bodies evaluate top-to-bottom.

**Verified:** full DI container resolution (all 6 tools registered, correct LLM-visible schemas — confirmed `search_knowledge_base`'s schema is exactly `{"query": ...}`, `search_document`'s is `{"query": ..., "document_id": ...}`, both correctly excluding `state`); full import sweep clean (404/427 OK, same pre-existing 23 failures, one new file added); and a direct tool invocation against the real Chroma vector store using this session's own previously-ingested test document (`ZBR-9410`/`FLX-77Q2`) — both `search_knowledge_base` and a chained `search_document` call returned correct, real chunk content. **Not verified:** an actual end-to-end chat request where the model itself chooses to call either tool — Postgres was unreachable in this environment for this whole pass, blocking a live server run; this is an environment limitation, not a code gap, and is flagged as such rather than silently skipped.

Tools (Phase 10) moves from 66.7% to **100%** — the fourth full phase this project has ever completed, after Memory, Document Processing, and Production Retrieval. **Overall score: 68.1%, a new all-time high.** `docs/ARCHITECTURE_TUTORIAL.md` and `docs/EXTENDING.md` both updated with the new tools and the `InjectedState`-for-tenant-scoped-tools pattern as a documented, repeatable approach for the next tool that needs per-request data.

---

## Session Management (Phase 6) completed — Conversation History and Persistent Sessions, the last two gaps, both closed for real

Asked to complete Session Management. Two gaps: Conversation History (messages were always persisted, just no HTTP-reachable read path) and Persistent Sessions (LangGraph's checkpointer was `MemorySaver`, in-memory only). Confirmed the checkpointer backend choice with the user before building (Postgres via `langgraph-checkpoint-postgres`, reusing the existing datastore, vs. Redis via `langgraph-checkpoint-redis` — Postgres won).

**Conversation History.** New `GET /api/v1/conversations/{id}/messages` (`packages/api/routers/conversations.py`) — paginated (`limit`/`offset`, capped at 200), oldest-first, tenant-scoped (`404` for both a nonexistent conversation and one belonging to another tenant, so existence can't be leaked to a non-owner). Reused `MessageRepository.list_by_conversation()`/`.count_by_conversation()`, both already real and correct — this was purely a missing HTTP surface. Also added `GET /api/v1/conversations/{id}` (single conversation metadata) since it was nearly free and was already the top-flagged suggested priority for the Conversation API's own "create + read" acceptance bar. New `MessageResponseSchema`/`ConversationHistoryResponseSchema` in `packages/api/schemas/conversation.py`.

**Persistent Sessions — the more involved half.** New `create_postgres_checkpointer()` (`packages/infrastructure/container/graph.py`) wires a real `AsyncPostgresSaver` (`langgraph-checkpoint-postgres`, a new dependency, pulling in `psycopg`/`psycopg-pool`). Two real design constraints discovered and worked around, not assumed away:

1. **`AsyncPostgresSaver.from_conn_string()` is an async context manager, not a plain constructor** — and `dependency_injector`'s async `providers.Resource` (the natural-looking DI fit) always returns an awaitable on every call, even after initialization, confirmed via a standalone test before committing to a design. The surrounding provider graph (`GraphBuilder`, itself `Factory`-wired) has no way to await that transparently. Solved by using `AsyncPostgresSaver`'s plain, synchronous `__init__(conn, serde=...)` instead — opening a real `psycopg.AsyncConnection` explicitly at app startup and overriding the DI container's `checkpointer` provider with the fully-constructed instance via `container.graph.checkpointer.override(providers.Object(checkpointer))`, in `packages/api/lifespan.py`. This is the exact same override pattern this codebase already established for per-request database sessions (`request_scoped_session`), just applied at application lifetime instead of per-request. The `MemorySaver` default stays declared as the fallback for any code path that constructs `ApplicationContainer()` directly without running through `lifespan()` (this session's own many ad-hoc verification scripts among them).
2. **A real platform bug: psycopg's async driver can't run under Windows' default `ProactorEventLoop`, and `uvicorn` hardcodes exactly that loop on native Windows regardless of any event-loop policy set at the application level** — confirmed by reading `uvicorn.loops.asyncio.asyncio_loop_factory`'s actual source, not assumed from the error message alone. An initial fix attempt (`asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())` in `packages/api/app.py`) was tested, found ineffective against uvicorn's hardcoded factory, and removed rather than left in as dead, misleading code. The checkpointer setup is wrapped in its own non-fatal `try`/`except` (mirroring the existing graph.png-render "never block startup" idiom) — falls back to in-memory with a clear log line, exactly as it does on this native-Windows dev machine every time. Confirmed this is a native-Windows-without-Docker limitation only: Linux's `asyncio_loop_factory` returns a normal `SelectorEventLoop`, so the real Docker deployment target (`docs/DEPLOYMENT.md`) is unaffected.

**Verified, both halves:** a live server confirmed both new conversation routes end to end — a 2-turn conversation's full 4-message history returned correctly ordered, wrong-tenant/nonexistent-ID requests both correctly `404`, and existing chat/RAG citation behavior unaffected (regression-checked). For the checkpointer specifically, since `uvicorn` can't exercise it on this machine: a **direct script proof of genuine cross-restart persistence** — wrote a real checkpoint via one `psycopg` connection, closed it (simulating process exit), then read the identical data back via a **second, entirely separate connection** (simulating a fresh process after restart) — the literal roadmap requirement, proven independent of the uvicorn/Windows limitation. Full import sweep clean (404/427 OK, zero new failures).

Session Management (Phase 6) moves from 50.0% to **100%** — the fifth full phase this project has ever completed, after Memory, Document Processing, Production Retrieval, and Tools. The new `GET /conversations/{id}` route also moves the Conversation API (Phase 14) from Partial to Done. **Overall score: 70.6%, a new all-time high.**

---

## Follow-up, same day: the Windows/uvicorn checkpointer limitation was fixable, and got fixed for real

The user pushed back on the entry above's "genuine platform limitation" framing: "we already have database connected" — a fair challenge, since the rest of the app (asyncpg-based DB access, real chat, real memory) already works fine under `uvicorn` on this exact native-Windows machine. The premise that *no* Postgres client could work there was wrong — only psycopg's specific *async* mode has the `ProactorEventLoop` restriction; asyncpg doesn't share it, and neither does psycopg's own *synchronous* mode.

Checked whether `langgraph-checkpoint-postgres` offers a sync alternative — it does: `langgraph.checkpoint.postgres.PostgresSaver`, the non-`.aio` sync counterpart to `AsyncPostgresSaver`, built on plain (non-async) psycopg connections. Plain sync connections don't participate in the event loop at all — they just block whatever thread calls them — which is exactly what `asyncio.to_thread()` is for.

Built `ThreadedPostgresSaver` (`packages/infrastructure/container/graph.py`), a small `BaseCheckpointSaver` subclass wrapping a `PostgresSaver` instance: `aget_tuple`/`alist`/`aput`/`aput_writes`/`adelete_thread` each delegate to the corresponding sync method via `asyncio.to_thread()`. This reuses the exact same real, tested checkpoint schema and protocol `langgraph-checkpoint-postgres` already implements — no reimplementation of checkpoint serialization or versioning from scratch, just a different transport underneath it (a plain `psycopg.Connection` instead of `psycopg.AsyncConnection`). `create_postgres_checkpointer()` was updated to open the connection and run `.setup()` via `asyncio.to_thread()` too, and `packages/api/lifespan.py`'s shutdown cleanup updated to close the now-sync connection the same way.

**Verified, decisively, not just plausibly:** ran the exact same write-then-read-via-a-separate-connection proof from the entry above, this time under the **default** event loop policy (no `WindowsSelectorEventLoopPolicy` override) — succeeded. Then started the real app via `uvicorn packages.api.app:app` with zero special flags and confirmed the startup log now reads `Persistent (Postgres-backed) checkpointer ready.`, not a fallback warning. Ran a full regression on top of that: a fresh chat turn, a same-conversation follow-up (confirming thread-scoped continuity still works with the real checkpointer active, not just the in-memory one), and the RAG citation flow (`ZBR-9410` query) — all correct. Full import sweep clean, zero new failures.

Corrected the "genuine, environment-specific limitation" framing everywhere it was written down this same day: `docs/BUILD_STATUS.md`, `docs/ARCHITECTURE_TUTORIAL.md`, `docs/TESTING_PLAYBOOK.md`, and `docs/DEPLOYMENT.md` all now describe the checkpointer as working on every platform, including native Windows — not degrading gracefully around a limitation that turned out to be fixable. Left this changelog's own earlier entry unedited, as the historical record of how the investigation actually unfolded — correcting it in place would erase the fact that the first attempt reached a wrong conclusion before being challenged and fixed properly.

---

## Document uploads now go through the real Upload Service, not local disk

Asked why document upload wasn't using `packages/sdk/upload` — the user's own answer was direct: they built a separate Upload Service specifically so uploaded files wouldn't pile up indefinitely in this app's own local storage folder. Investigated why it was disconnected: `packages/sdk/upload/client.py` imported `UploadSettings` from `packages.config.upload`, a module that has never existed (the real settings live at `packages/config/upload_service.py`, class `UploadServiceSettings`) — this was already flagged as broken-and-unused in `docs/UNUSED_FILES.md`, and nothing in the DI container ever constructed a `UploadClient` in the first place.

**Fixed both problems.** The one-line import correction in `client.py`. Then a new `packages/infrastructure/container/upload.py` (`UploadContainer`) — `providers.Singleton(create_http_client)` → `providers.Singleton(UploadClient, client=http_client, settings=app_settings.upload_service)`, the exact same shape `packages/infrastructure/container/iam.py` already established for the IAM SDK — wired into `ApplicationContainer` as `container.upload`.

**Rewired `POST /api/v1/documents` (`packages/api/routers/documents.py`) around it.** The route now reads the incoming file once, uploads it to the Upload Service via `container.upload.client().uploads.upload(...)` — the durable copy, on a separate service by design — and only then writes a **local scratch copy** (`settings.storage.temp_directory`, not `upload_directory`) purely because the existing loader/splitter ingestion pipeline (`packages/knowledge/pipelines/ingestion.py`) needs a real local `Path` to read from. That scratch file is deleted in `_ingest_in_background`'s `finally` block once ingestion finishes — success, failure, or skipped-as-duplicate all clean up the same way — so nothing accumulates locally anymore, closing the exact gap the user raised. A connection failure or non-2xx response from the Upload Service now fails the whole upload request with a `502`, rather than silently falling back to local-only storage — the same "don't quietly degrade a feature that's supposed to be real" lesson from the checkpointer entry above applies here: the point of building a separate Upload Service is for it to actually be the source of truth, not an optional nicety.

**`Document.file_id` is now real.** That column existed since this table was first modeled, but `packages/knowledge/pipelines/ingestion.py`'s `_create_document_row()` always filled it with a throwaway `uuid4()` — nothing was ever behind it. `IngestionRequest` (`packages/knowledge/schemas.py`) gained a `file_id: UUID | None` field, threaded through from the Upload Service's real response; `_create_document_row()` now uses `request.file_id or uuid4()` (the fallback only matters for callers that construct an `IngestionRequest` directly without going through the real upload route). `DocumentUploadResponseSchema` also gained a `file_id` field so callers can see it immediately, not just after querying the document later.

**Verified live, end-to-end, against a real running app** — not just import-clean. Stood up a minimal stand-in Upload Service (matching the real one's `POST /api/files/upload` contract) since this project's own `.env` currently has `UPLOAD_SERVICE_URL` pointed at LangSmith by mistake (a previously-known, deliberately-unfixed placeholder — see `docs/BUILD_STATUS.md` §13). With `UPLOAD_SERVICE_URL` overridden to point at it: uploaded a real file through the actual running app, confirmed the response returned a real Upload-Service-issued `file_id`, confirmed background ingestion completed and `Document.file_id` in Postgres **exactly matched** that same ID, and confirmed the local scratch file was gone afterward. Re-uploaded the identical content a second time and confirmed the checksum-based dedup path in `IngestionPipeline.ingest()` still correctly skips re-indexing (`skipped=True`, zero new chunks, same `document_id` reused) even though the Upload Service — which doesn't dedup at the storage layer — issued a second, different `file_id` for the redundant physical copy; storage durability and indexing-cost avoidance are treated as separate concerns, deliberately. Full import sweep: 10 pre-existing failures (down from 11 — fixing the broken import removed one of them), zero new failures.

Updated `docs/UNUSED_FILES.md` (`packages/sdk/upload/` moved off the confirmed-unused/broken list) and `docs/ARCHITECTURE_TUTORIAL.md` (§5.1 rewritten, new §13 entry). **Still open, flagged rather than silently left:** the real `.env`'s `UPLOAD_SERVICE_URL` needs pointing at an actual running Upload Service instance before this works outside of a test that overrides the env var — the code now genuinely depends on it being correct, where before it was inert.

---

## Follow-up, same day: pointed at the real Upload Service — its actual API contract didn't match the SDK at all

The user updated `.env`'s `UPLOAD_SERVICE_URL` to the real, running Upload Service (`https://fms.easydev.in`), replacing the LangSmith-URL placeholder flagged above and in `docs/BUILD_STATUS.md`. Before assuming the previous pass's SDK fixes would just work against it, probed the real service directly (`/health`, `/api/files/upload`, `/api/files`, `/api/files/{id}`, `/api/files/{id}/download`) — good thing this wasn't skipped, because **the SDK's models and request shape were both wrong**, not just the broken import from the prior pass:

- **Multipart field name.** `packages/sdk/upload/uploads.py` sent the file under form field `file`; the real service rejects that (`"Unexpected field 'file'"`) and expects `files` — plural, even for one file.
- **Response envelope.** Every real response wraps its payload in `{success, message, data, timestamp, requestId, statusCode, status}`. The SDK was validating its models directly against the raw response body, not `data` — would have raised a pydantic validation error on every single call.
- **`id` is a Mongo ObjectId string, not a UUID.** The real service (confirmed via `/health/ready`: `"mongodb":"ok"`) issues 24-character hex ObjectId strings as file IDs — `packages/sdk/upload/models.py`'s `UploadedFile.id: UUID` would have rejected every real response outright.
- **Field names are camelCase** (`tenantId`, `originalName`, `storageKey`, `mimeType`, `scanStatus`, `createdAt`, `updatedAt`) with a materially different shape than assumed — no `bucket`/`storage_provider`/`object_key`/`checksum`/`is_deleted`/`version` fields exist; instead there's `storageKey` (a single combined path), `status` (a string, not a bool), and a nested `metadata` object with its own `description`/`tags`/`custom`/`title`/`altText`/`author`/`source`/`language`/`isPublic`/`linkedTo` fields.
- **The service maintains its own file-type allowlist.** Confirmed live: `application/pdf` is accepted; `text/plain` and `application/octet-stream` are both rejected with a `415`.

**Fixed all of it.** Rewrote `UploadedFile` (`packages/sdk/upload/models.py`) with the real field names via Pydantic aliases (`Field(alias="tenantId")` etc.), added a `FileMetadata` submodel matching the real nested shape, and changed `FileListResponse.items` → `.files` to match the real list endpoint. Added `BaseClient._unwrap()` (`packages/sdk/common/base_client.py`) — every SDK method that previously did `Model.model_validate(response.json())` now does `Model.model_validate(self._unwrap(response))`, pulling `data` out of the envelope first. Fixed the multipart field name to `files` in `uploads.py`, and its response parsing to take `data[0]` (upload always returns a list). Left the presigned-upload/multipart-chunking methods (`create_presigned_upload`, `initiate_multipart`, etc.) as unverified — nothing observed about this service (a Mongo-backed, direct-multipart-only design per its own health check) suggests it implements S3-style presigned/chunked uploads, and there was no way to test them without guessing at a contract with zero live evidence behind it; marked clearly in a code comment rather than left ambiguous.

**A real, cascading schema fix.** Since `UploadedFile.id` is a Mongo ObjectId string, not a UUID, and `Document.file_id` (`packages/domain/models/document.py`) is a Postgres `uuid` column, the very first real upload against the real service would have crashed on insert. Changed `file_id` to `String(64)`, applied live via `ALTER TABLE documents ALTER COLUMN file_id TYPE VARCHAR(64) USING file_id::text` (this project's established manual-migration pattern — see `docs/DEPLOYMENT.md` §3 — confirmed all 7 existing rows' previously-fake `uuid4()` values survived the cast unchanged, just as strings now instead of UUIDs). Threaded the type change through `IngestionRequest.file_id` (`packages/knowledge/schemas.py`) and `DocumentUploadResponseSchema.file_id` (`packages/api/schemas/document.py`), both `UUID` → `str`.

**Improved error surfacing in `packages/api/routers/documents.py`** now that a real service is behind this: a connectivity failure (`httpx.HTTPError` — service unreachable) still returns `502`, but a response the service actively rejected (`SDKException` — e.g. a disallowed file type) now returns `400` with the service's own real message (`"File type text/plain not allowed"`), instead of both cases collapsing into the same generic "check UPLOAD_SERVICE_URL" `502` from the prior pass, which would have been actively misleading for a rejected-file-type case.

**Verified live, against the real `https://fms.easydev.in`, not a stand-in this time.** Uploaded a real PDF through the actual running app — got back a real Mongo ObjectId `file_id` (`6a607c55...`), confirmed `201 Created` from the real service in the app's own logs, confirmed background ingestion completed (6 pages loaded, 17 chunks), and confirmed `Document.file_id` in Postgres matches the real service's ID exactly. Confirmed the local scratch file was cleaned up. Confirmed the file-type rejection path: uploading a `.txt` file now correctly surfaces `400 — "File type text/plain not allowed"` instead of a generic error. Full import sweep: same 10 pre-existing failures, zero new ones.

**Worth knowing going forward:** the real Upload Service rejects `text/plain` — a format this project's own ingestion pipeline otherwise supports (`packages/knowledge/loaders/text.py`). Plain-text document uploads will now genuinely fail at the Upload Service step with a clear `400`, not silently succeed — this is a real constraint of the service being integrated, not a bug in this pass's code, and is worth knowing before assuming ".txt uploads work end to end" the way they did when uploads just wrote to local disk.

---

## Follow-up, same day: checked the SDK against the Upload Service's own written integration guide — found (and fixed) a real tenant-isolation bug

Asked to align `packages/sdk/upload/` against `file-upload-service/docs/INTEGRATION_GUIDE.md` — the authoritative, hand-written contract doc for the real service, one directory over from this repo. Read it in full and diffed it against everything built in the previous two passes. It confirmed most of the prior fixes (envelope wrapping, `files` field name, Mongo ObjectId IDs, camelCase fields) but surfaced several things neither live probing nor guessing had caught:

**The most serious one: nothing was sending `X-Tenant-Id` or `X-User-Id` at all.** The guide is explicit (§4): this service does zero authentication of its own — it trusts these two headers completely, and silently falls back to its own `DEFAULT_TENANT_ID` if `X-Tenant-Id` is missing. Every test upload in the prior two passes landed under that service's default tenant (`"easydev"`, confirmed by listing files on the real service with no tenant filter and finding them there) — **not** under this app's own per-tenant `tenant_id`, meaning multi-tenant isolation was completely bypassed at the Upload Service layer, the whole time, for every real upload. Fixed by making `tenant_id` a required keyword argument on `UploadUploadsSDK.upload()` (not optional — silently omittable is exactly the bug) and threading it, plus optional `user_id`, through every method on `UploadFilesSDK` and `UploadUploadsSDK` via a new `packages/sdk/upload/_headers.py::identity_headers()`. `packages/api/routers/documents.py` now passes the request's real `tenant_id`/`user_id` into the upload call. **Verified live**: uploaded a file with a distinct tenant/user ID pair, then listed files on the real service scoped to that exact tenant — the file showed up there, with the correct `storageKey` path (`files/{tenant}/{user}/...`) and `uploader` field, and did *not* appear when listing without a tenant filter (only pre-existing "easydev"-tenant files did).

**Two real, previously-uncaught request-shape bugs, both would have failed every single call:**
- `RenameFileRequest` sent `{"filename": "..."}`; the real endpoint (`PATCH /api/files/:id/rename`) wants `{"name": "..."}`. Fixed the field name; verified live — a real rename against the real service succeeded and the returned `originalName` matched.
- `UpdateMetadataRequest` was flat (`{metadata: {...}, tags: [...]}`); the real endpoint (`PATCH /api/files/:id`) wants `originalName`/`category` at the top level and everything else (`description`/`title`/`altText`/`author`/`source`/`language`/`expiresAt`/`isPublic`/`tags`/`custom`/`linkedTo`) nested under `metadata`. Rewrote as `UpdateMetadataRequest`/new `MetadataUpdate`, added `by_alias=True` to the `.model_dump()` call (needed separately — aliases don't apply on serialization without it, only parsing). Verified live — a real metadata update succeeded and the new description/tags round-tripped correctly.

**A response-shape bug specific to two mutating endpoints:** `rename()`/`update_metadata()` were unwrapping the envelope's `data` and treating it as the file object directly — but the guide (§7) documents both of these specific endpoints as returning `{data: {file: {...}, requestId: "..."}}`, one level deeper than every read endpoint. Fixed both to pull `data["file"]`. Confirmed this really is different per-endpoint, not a doc inconsistency: the same live test that fixed the field-name bugs above also confirmed the response nesting.

**Two more undocumented gotchas the guide itself doesn't mention, found only by testing against the real, running service:**
- `GET /api/files/:id` — the guide lists `X-User-Id` as optional here, but the real service 404s ("File not found") on a file that demonstrably exists and belongs to the given tenant, unless `X-User-Id` is also sent. Added `user_id` as an optional parameter to `get_file()`/`download()`/`delete()`/`permanent_delete()`/`get_transactions()` (previously only `rename()`/`update_metadata()` had it) so it can be supplied wherever available, not just where the guide says it's needed.
- `GET /api/files/:id/transactions` — 401s live with `"Admin authentication required"`, using the exact same tenant/user pair that worked for every other endpoint. Not mentioned anywhere in the guide's own docs for this route. Left `get_transactions()` as-is with a comment explaining the finding, since nothing in this app calls it and there's no admin-auth mechanism wired into `UploadServiceSettings` to fix it properly yet.
- `list_files()` had its own bug, caught only by actually calling it: it always sent `search` as a query param, even `None` — and the real service's Joi validation rejects an empty `search` param outright (`"search" is not allowed to be empty`). Fixed to omit the param entirely when not provided.

**Confirmed, definitively this time, that presigned-upload/multipart-chunking (`create_presigned_upload`, `initiate_multipart`, etc.) and all of `bulk.py` don't correspond to any real endpoint.** The guide's §7 is an exhaustive endpoint list — upload, list, get, download, rename, update, replace, delete, permanent-delete, transactions, health — and none of those flows appear anywhere in it. Previously this was a reasonable inference from what `/health/ready` didn't mention; now it's a documented fact, and both files' comments were updated to say so plainly instead of hedging.

**Added `replace()`** (`PUT /api/files/:id/replace`) — a real, documented endpoint with no prior SDK method at all. Its multipart field is `file` (singular) — the exact opposite of `upload()`'s `files` (plural), a mismatch the guide's own troubleshooting section (§14) calls out as a common integration mistake.

**Also fixed `FileTransaction`** to match the guide's Transaction Object Shape exactly (`_id`/`tenantId`/`fileId`/`operation`/`performedBy`/`payload`/`providerResponse`, all previously wrong field names left over from the original speculative model), and added `AliasChoices("url", "publicUrl")` to `UploadedFile.url` since the real service is inconsistent about which name it uses across endpoints (confirmed live: `url` on upload/get-by-id, `publicUrl` on list) — the guide's own examples show `publicUrl` even where live behavior returned `url`.

**Also worth knowing:** the guide's own troubleshooting section documents `MAX_FILE_SIZE` defaulting to 10MB on the real service, versus this project's own `StorageSettings.max_file_size` defaulting to 50MB — a 20-40MB file would pass this app's own validation and then get rejected by the Upload Service with a `413`. Not fixed (no evidence of the real deployed service's actual configured limit, only the guide's stated default), just flagged.

Full import sweep after all of this: same 10 pre-existing failures (397 modules now, +1 for the new `_headers.py`), zero new ones. Every fix in this entry was verified against the real, live `https://fms.easydev.in`, not asserted from reading the guide alone — upload, get, list, rename, and update-metadata were all exercised live end-to-end with real tenant/user IDs.
