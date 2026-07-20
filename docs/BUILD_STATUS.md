# Build Status — MVP v1.0

Verified against [`docs/mvpRAG.md`](./mvpRAG.md) — that file is the **target roadmap** (what's in scope for v1.0/v1.1/v2.0 and why); this file is the **reality check** (what's actually built, working, broken, or missing right now). Read them as a pair: mvpRAG.md's ✅ marks mean "in v1.0 scope," not "done" — this document is where "done" gets verified.

Eleventh audit pass, HEAD `0d3309e` + 6 uncommitted modified files, re-verified 2026-07-20. **Process note, repeated from last pass:** the working tree was being actively edited live during this audit (again) — a background verification agent's report and my own direct follow-up testing minutes later disagreed on several points because fixes landed in between. Everything below reflects the most recent, directly-confirmed state.

**Headline finding this pass — two of the three app-breaking bugs from last pass are genuinely fixed, the app imports and starts, and the health endpoint is fully live. But chat still 500s, now on a different, deeper bug.**

Fixed, confirmed live:
- **The `packages/graph/nodes.py`/`packages/graph/nodes/` collision** is resolved — the old file was renamed out of the way (to `packages/graph/nodessss.py`, now dead/orphaned code, not a clean deletion, but the collision itself is gone), and `packages/graph/__init__.py`/`packages/infrastructure/container/graph.py` no longer import the `NodeContext` name that briefly replaced this bug mid-pass. `import packages.graph` and `from packages.api.app import app` both succeed now, confirmed directly.
- **`packages/rag/builders/__init__.py` and `packages/rag/pipelines/__init__.py`** are both fixed — real, empty `# init` files, no more stray `MemoryManager` reference. Confirmed: `from packages.rag.builders.context import ContextBuilder` and friends all import cleanly now.
- **The same copy-paste bug in `packages/middleware/__init__.py`, `packages/planner/__init__.py`, `packages/memory/implementations/__init__.py`** — all three fixed too.

**Confirmed live via `TestClient`:** `GET /api/v1/health` → **200**, `{"database":"healthy","redis":"healthy"}` against real, reachable services in this environment — the most solid this endpoint has ever been proven. But `POST /api/v1/chat` → **500**. Root cause, traced directly: `packages/infrastructure/container/memory.py` wires `MemoryManager(factory=checkpoint)`, but the real `MemoryManager.__init__` (`packages/memory/manager.py:49-55`) takes `(store, extractor, summarizer, retriever)` — no `factory` parameter exists at all. This is a pre-existing bug (not new this pass) that was previously masked by the graph-import-level outage; now that those are fixed, this is the next bug actually reached. It fails before the DI container even gets to constructing the graph/nodes chain, let alone the LLM — so `GoogleProvider`'s `api_key=` fix (confirmed correct two passes running now) still can't be demonstrated live.

**Not resolved this pass, despite the commit message claiming "remove unused files":** every item on `docs/UNUSED_FILES.md`'s confirmed-unused list is still present (`packages/application/`, `packages/sdk/upload`/`notification`/`common/models.py`, `infrastructure/ai/factory.py`, `requirements.txt`, `graph.png`) and the two junk zip archives (`packages.zip`, `packages/graph.zip`) are still committed to git history with no follow-up removal. The commit's actual diff doesn't touch any of these files.

**Also unresolved:** the `PlannerResult` duplicate-class collision (two different classes, one in `packages/graph/planner.py`, one in `packages/graph/nodes/planner.py`, both still referenced) — a new `GraphToolNode` class landed (`packages/graph/nodes/tool.py`) but is real, dead code, never constructed by anything (the actual `tool` field uses LangGraph's own `ToolNode` directly instead). The DB session `providers.Resource`/`Factory` bug, `EmbeddingSettings` missing `provider`, and the `packages/knowledge/splitters/` `DocumentSplitter`/`BaseSplitter` mismatch are all unchanged.

- Modules importing cleanly (fresh sweep, just now): **415 / 441 (94.1%)** — up from 343/440 (77.9%) last pass, the healthiest sweep across all eleven passes. All 26 remaining failures are the same pre-existing, already-tracked issues (stale `AgentState` imports, `sdk` bugs, `knowledge/splitters` mismatch, dead `ai/factory.py`, one new-but-unwired `packages.middleware.memory` `NameError`).

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
| 1 — Foundation | 11 | 7 | 3 | 1 | 0 | **63.6%** ▲▲ |
| 2 — IAM | 7 | 2 | 0 | 0 | 5 | **28.6%** ▲ |
| 3 — Database | 12 | 8 | 0 | 0 | 4 | **66.7%** |
| 4 — LangChain | 10 | 1 | 0 | 6 | 3 | **10.0%** |
| 5 — LangGraph | 9 | 2 | 3 | 1 | 3 | **22.2%** ▲ |
| 6 — Session Management | 4 | 0 | 2 | 1 | 1 | **0.0%** |
| 7 — Memory | 5 | 0 | 1 | 0 | 4 | **0.0%** |
| 8 — Document Processing | 15 | 0 | 10 | 0 | 5 | **0.0%** |
| 9 — Production Retrieval ⭐ | 13 | 0 | 4 | 0 | 9 | **0.0%** |
| 10 — Tools | 6 | 1 | 3 | 0 | 2 | **16.7%** |
| 11 — Human in the Loop | 3 | 0 | 0 | 0 | 3 | **0.0%** |
| 12 — Background Jobs | 5 | 1 | 1 | 0 | 3 | **20.0%** ▲ |
| 13 — Production hardening | 5 | 3 | 0 | 0 | 2 | **60.0%** ▲ |
| 14 — APIs | 7 | 0 | 0 | 1 | 6 | **0.0%** |
| 15 — Testing | 4 | 0 | 0 | 0 | 4 | **0.0%** |
| 16 — Deployment | 3 | 0 | 3 | 0 | 0 | **0.0%** |
| **Total** | **119** | **25** | **30** | **10** | **54** | **21.0%** ▲▲ |

**Overall: 21.0% done · 25.2% partial · 8.4% broken · 45.4% pending** (25 / 30 / 10 / 54 out of 119 roadmap items) — a sharp recovery from 10.9% last pass, just short of the ninth pass's all-time high (26.9%). Broken dropped from 15 to 10 items.

**Why most phases recovered even though chat still doesn't work:** Foundation, IAM, Background Jobs, and Production hardening all bounced back because the app genuinely imports and starts again, and `GET /api/v1/health` is now provably live (`database: healthy, redis: healthy` against real services in this environment) — the strongest proof that endpoint has ever had. But LangChain, LangGraph, Session Management, and APIs are still stuck broken, because `POST /api/v1/chat` still 500s — just on a new, deeper bug (`packages/infrastructure/container/memory.py`'s `MemoryManager(factory=...)` mismatch) that was previously hidden behind the two now-fixed import-level bugs. Pending barely moved (55→54) — nothing from `docs/UNUSED_FILES.md` was actually cleaned up despite a commit message claiming otherwise.

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

**Still Broken this phase:** Dependency injection — `database`, `tools`, and `ai` container branches construct fine, but `memory`/`graph` still fail (see Broken → `MemoryManager(factory=...)` mismatch). **Still Partial:** CLI, Docker, Docker Compose — unchanged.

### Database
| Item | Evidence |
|---|---|
| Conversation & Message models, Knowledge Base / Document / Chunk models, Prompt Templates, Embeddings Metadata, Model Configurations, repository layer | Unaffected throughout — confirmed again this pass via the live, healthy DB connection at the health endpoint. |

### LangChain
| Item | Evidence |
|---|---|
| Document objects | Unaffected. |

**Still Broken:** Chat Models, Gemini, Embeddings, OpenAI, Anthropic, Groq — the live chat path still 500s before it ever reaches LLM construction (see Broken → the `memory` container bug blocks `graph.manager()`, which blocks everything downstream of it). `GoogleProvider`'s `api_key=` fix is still believed correct (confirmed unchanged in the code) but remains unprovable live for a third pass running, now for yet another reason blocking it upstream.

### LangGraph
| Item | Evidence |
|---|---|
| Nodes & package wiring — recovered | `packages/graph/nodes/` (the new per-class package: `RetrieveNode`, `LLMNode`, `LoadMemoryNode`, `ExtractMemoryNode`, `GraphPlanner`, plus a real `GraphNodes` dataclass tying them together) now imports cleanly and is structurally sound. Confirmed via direct import and the fresh sweep. |
| GraphState | Imports cleanly; the `PlannerResult` type reference is now behind a `TYPE_CHECKING` guard so it no longer risks a circular-import crash (though see Broken — the underlying duplicate-class issue is still unresolved). |

**Still Broken:** Conditional routing / graph construction via DI — `container.graph.manager()` no longer fails on an import error, but fails one layer deeper: building the `context` provider requires resolving `memory.manager`, which is itself broken (see Broken section). **Still Partial, unaffected:** Reducers, Checkpointing, Streaming.

### Session management
| Item | Evidence |
|---|---|
| No more duplicate user message (fix retained) | Unaffected. |

**Still Broken:** Chat Sessions — `POST /api/v1/chat` still doesn't complete a real turn; confirmed live it now 500s on the `memory` container bug rather than an import-time crash, which is progress (one layer closer), but the live, full-turn proof from the ninth pass still isn't reproducible.

### Tools
| Item | Evidence |
|---|---|
| Tool registry population, tool executor signature | Structurally unchanged. |
| **Calculator — fixed, confirmed still working** | Unaffected by this pass's changes; re-confirmed live. |

**Still Partial:** Web search and Weather — tool code itself is fine, but the live, through-the-app proof still isn't obtainable since chat itself doesn't complete a turn.

### Background jobs / Production
| Item | Evidence |
|---|---|
| Configuration management | Unaffected. |
| Redis connectivity — recovered, most solid proof yet | Confirmed live via the health endpoint: `"redis":"healthy"` against a real, reachable Redis in this environment. |

---

## 🔴 Broken — real code exists but currently fails

### Chat still 500s — a new, deeper bug, reached now that the app-wide outage is fixed

| Item | File(s) | What's wrong |
|---|---|---|
| **`MemoryManager` constructed with a nonexistent `factory` argument** | `packages/infrastructure/container/memory.py`, `packages/memory/manager.py:49-55` | Now the single highest-priority bug in the repo — the direct cause of `POST /api/v1/chat`'s `500`. `MemoryContainer.manager = providers.Singleton(MemoryManager, factory=checkpoint)` — but the real `MemoryManager.__init__` takes `(store, extractor, summarizer, retriever)`, no `factory` parameter at all. Confirmed live: `container.graph.manager()` raises `TypeError: MemoryManager.__init__() got an unexpected keyword argument 'factory'`, because the graph's `context` provider depends on `memory.manager` as one of its own dependencies. This is a pre-existing bug (not introduced this pass) that was simply unreachable until the two `packages/graph/`/`packages/rag/` import bugs got fixed — it was always going to be the next blocker in line. Fix: either wire `MemoryContainer.manager` to construct real `MemoryStore`/`MemoryExtractor`/`MemorySummarizer`/`MemoryRetriever` instances (the real, substantial pgvector-backed implementations already exist in `packages/memory/implementations/` from an earlier pass, just never wired here), or change `MemoryManager`'s constructor if `factory`/`checkpoint`-based construction is the actually-intended design. |
| **DB session provider still shares one session across every request** | `packages/infrastructure/container/database.py` | Unchanged for three passes running: `session = providers.Resource(...)` instead of `providers.Factory(...)`. Confirmed live: calling it twice returns the identical `AsyncSession` object. Currently masked by the bug above (nothing reaches this far in the live chat path yet), but will be the next thing to fix once `MemoryManager` is corrected. |
| **`GoogleProvider`'s `api_key=` fix — still correct, still unprovable, third pass running** | `packages/infrastructure/ai/providers/google.py` | Unchanged, confirmed still correctly passing `api_key=settings.ai.google_api_key`. Still can't be demonstrated live — the `MemoryManager` bug above now blocks the path before it ever reaches LLM construction. |
| **Two different `PlannerResult` classes, referenced inconsistently — unresolved** | `packages/graph/planner.py` vs `packages/graph/nodes/planner.py` | Unchanged from last pass: the old `planner.py`'s `PlannerResult(next_node: str)` and the new `nodes/planner.py`'s `PlannerResult(next_node: NextNode, reason: str)` both still exist. `state.py` types against the old one (now behind a `TYPE_CHECKING` guard, so it no longer risks a circular-import crash — that specific symptom is fixed — but the underlying duplication is not); `router.py` imports the enum from the new one. A fourth instance of the same-name-different-class pattern tracked in `docs/UNUSED_FILES.md` alongside `RetrievalPipeline` and `ChatService`. |
| **`GraphToolNode` — new, real, but dead code** | `packages/graph/nodes/tool.py` | A real, working async wrapper around LangGraph's own `ToolNode`. But confirmed via repo-wide grep: nothing constructs or references it. `packages/graph/nodes/__init__.py`'s own `tool` field is typed against LangGraph's `ToolNode` directly, imported separately — `GraphToolNode` is unused scaffolding, same "wired but never consumed" pattern as `packages/knowledge/`'s dead leaves. |
| **The old `nodes.py` was renamed, not deleted** | `packages/graph/nodessss.py` | The collision with the new `packages/graph/nodes/` package is genuinely resolved — but by `git mv`-ing the old file to a typo'd filename rather than finishing the migration cleanly or deleting it. It's now orphaned dead code (the old `GraphNodes`/`NodeContext` implementation), not referenced by anything. Worth a proper deletion rather than leaving a stray, oddly-named file behind. |
| **"Remove unused files" — commit message not substantiated by the actual diff** | — | Checked every item on `docs/UNUSED_FILES.md`'s confirmed-unused list: all still present, unchanged — `packages/application/` (full package), `packages/conversation/store.py`/`memory_store.py`, `packages/infrastructure/ai/factory.py`, `packages/sdk/upload/`, `packages/sdk/notification/`, `packages/sdk/common/models.py`, `requirements.txt`, `graph.png`. The two junk zip archives (`packages.zip`, `packages/graph.zip`) are still committed to git history with no follow-up removal commit (`git log --all` for both still shows only the original commit that added them). None of these files appear in this batch's actual diff. |

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
| Stray debug `print()` statements, uncommitted | `packages/conversation/manager.py:73`, `packages/graph/planner.py`, `packages/graph/router.py`, `packages/tools/builtin/weather.py:153` | Still present, unchanged. `conversation/manager.py`'s prints raw user message content — same Windows-console-unicode crash risk as the (now-fixed) `GraphVisualizer` bug if a message contains certain characters. |
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
Only 2 of 9 planned routers are real and registered — and each of those two only has **a single route**, not a full resource API. Confirmed by reading `packages/api/routers/__init__.py` directly:

```python
from packages.api.routers.chat import router as chat_router
# from .conversations import router as conversation_router
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
# api_router.include_router(conversation_router)   # ... and 6 more, all commented out
```

**Chat router — only `POST /api/v1/chat` exists.** Verified by reading `packages/api/routers/chat.py` in full (52 lines): it defines exactly one route, `@router.post("", ...)` (lines 22-28), which takes a `ChatRequestSchema` (`conversation_id`, `message`, `stream`) and calls `ConversationManager.chat(...)`. There is no other route in this file — confirmed via `grep "@router\.(get|post|put|delete|patch|websocket)"` across the whole `routers/` directory, which returns only this one `@router.post` in `chat.py` and one `@router.get` in `health.py`. Specifically **missing** from the chat surface, even though the roadmap and the request schema imply them:

| Missing route | Evidence it's expected but absent |
|---|---|
| `GET /chat/{conversation_id}` or similar — fetch conversation/message history | No such route in `chat.py`; the only way to read back messages is directly from the DB |
| Streaming response (`GET`/`POST` with SSE, or a websocket) | `ChatRequestSchema` has a `stream: bool` field and `cli.py` always sends `stream: false` with a comment implying streaming isn't actually wired up server-side; `ConversationManager`/`GraphManager` do expose a `stream()` method (`packages/graph/manager.py:27-35`) but nothing in `chat.py` calls it — the field is accepted and silently ignored |
| `DELETE /chat/{conversation_id}` — end/delete a conversation | Not present |
| Conversation creation (`POST /conversations`) | Lives under the still-stubbed `conversations.py` router (see below), not `chat.py` — there is genuinely no HTTP-reachable way to create a conversation at all right now |

Each of the 7 unregistered router files (including `conversations.py`, which is where conversation creation/listing would actually belong) is a **single-line comment stub** (verified by reading each file directly):

| File | Full contents |
|---|---|
| `packages/api/routers/conversations.py` | `# Router conversations` |
| `packages/api/routers/documents.py` | `# Router documents` |
| `packages/api/routers/feedback.py` | `# Router feedback` |
| `packages/api/routers/knowledge_bases.py` | `# Router knowledge bases` |
| `packages/api/routers/models.py` | `# Router models` |
| `packages/api/routers/prompts.py` | `# Router prompts` |
| `packages/api/routers/search.py` | `# Router search` |
| `packages/api/routers/tools.py` | `# Router tools` |

**Practical impact:** the entire HTTP-reachable chat surface is one endpoint — send a message into an existing conversation, non-streaming, with no way to create that conversation, list its history, or delete it over HTTP. **And nothing is reachable at all this pass** — see Broken → the `packages.graph.nodes` / `packages.rag.builders` import failures — the app doesn't start, so even `GET /api/v1/health` cannot currently be reached.

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

The app starts now — one bug stands between here and a working chat request again:

1. **Fix `MemoryManager`'s constructor mismatch in `packages/infrastructure/container/memory.py`.** Wire real `MemoryStore`/`MemoryExtractor`/`MemorySummarizer`/`MemoryRetriever` instances instead of `factory=checkpoint` — the real pgvector-backed implementations already exist in `packages/memory/implementations/`, they just aren't connected to this container. This is the only thing currently blocking `POST /api/v1/chat`.
2. **Revert the DB session `Factory`→`Resource` change** in `packages/infrastructure/container/database.py` — the next bug in line once #1 is fixed.
3. **Reconfirm `GoogleProvider`'s `api_key=` fix live** — the code has been correct for three passes running; it just needs #1 and #2 fixed to finally be reachable.
4. **Reconcile the two `PlannerResult` classes** (`packages/graph/planner.py` vs `packages/graph/nodes/planner.py`) — pick one, delete the other, update `state.py`/`router.py` to agree.
5. **Delete the orphaned `packages/graph/nodessss.py`** (the old `GraphNodes`/`NodeContext` implementation, renamed out of the way rather than removed) and **`packages/graph/nodes/tool.py`'s dead `GraphToolNode`** if LangGraph's own `ToolNode` is the intended long-term path.
6. **Fix `EmbeddingSettings` missing `provider`**, and `packages/knowledge/splitters/{pipeline,recursive,factory}.py`'s `DocumentSplitter`/`BaseSplitter` mismatch — both still unchanged across four passes now.
7. **Actually clean up `docs/UNUSED_FILES.md`'s inventory** — a commit message claimed this happened; the diff shows it didn't. `git rm packages.zip packages/graph.zip graph.png`, delete `packages/application/`, `packages/sdk/upload/`, `packages/sdk/notification/`, `packages/sdk/common/models.py`, `infrastructure/ai/factory.py`, `requirements.txt`.
8. **Write an actual pytest suite.** Eleven audit passes in: a CI import-smoke-test alone (`python -c "from packages.api.app import app"`) would have caught the last two passes' headline regressions in under a second, for free.
9. **Restore the commit() calls in `packages/infrastructure/repositories/base.py`**, wire up at least the Conversations router, fix the Docker healthcheck path and Makefile paths, wire real JWT validation, and regenerate the Alembic "initial schema" migration properly.

**Fixed this pass:** `SafeCalculator`'s `ast.Num` crash and the `dataclass(slots=True)`/`__dict__` crash found alongside it — see Broken section for detail. One small, non-crashing gap remains (list-literal arguments to `sum`/`avg` aren't supported) but wasn't bundled into this fix.
