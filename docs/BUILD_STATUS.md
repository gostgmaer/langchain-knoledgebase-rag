# Build Status — MVP v1.0

Verified against [`docs/mvpRAG.md`](./mvpRAG.md) — that file is the **target roadmap** (what's in scope for v1.0/v1.1/v2.0 and why); this file is the **reality check** (what's actually built, working, broken, or missing right now). Read them as a pair: mvpRAG.md's ✅ marks mean "in v1.0 scope," not "done" — this document is where "done" gets verified.

Tenth audit pass, HEAD `e5d8709`, working tree clean, re-verified 2026-07-20. Note on process: mid-audit, the working tree that this pass started auditing (13 uncommitted files) was committed by something outside the audit itself — this doc now reflects the committed result, `e5d8709` ("Add initial implementations and structure for graph and memory packages").

**Headline finding this pass — the app cannot start, and last pass's "chat works end-to-end" milestone is not reproducible.** Two independent new bugs, both introduced by an in-progress refactor that wasn't finished before committing:

1. **`packages/graph/nodes.py` (a file) and `packages/graph/nodes/` (a new directory) now both exist in the same location.** Python resolves this deterministically in favor of the package — confirmed empirically: `import packages.graph.nodes` returns the directory's near-empty `__init__.py`, and `hasattr(it, 'GraphNodes')` is `False`. `packages/graph/builder.py` still does `from packages.graph.nodes import GraphNodes`, which now raises `ImportError`. Since `packages/graph/__init__.py` imports `GraphBuilder` at package level, **importing `packages.graph` at all now fails**, cascading into `packages/api/app.py` and everything downstream.
2. **`packages/rag/builders/__init__.py` and `packages/rag/pipelines/__init__.py`** — two more new files from the same refactor — are both a copy-pasted `from .manager import MemoryManager`, but neither directory has a `manager.py`. Confirmed broken directly: `ModuleNotFoundError: No module named 'packages.rag.builders.manager'`. This independently breaks `packages/infrastructure/container/rag.py` and `packages/rag/manager.py`.

Confirmed live: `from packages.api.app import app` raises `ImportError` via the first bug before a `TestClient` can even be constructed — `GET /api/v1/health` and `POST /api/v1/chat` could not be attempted at all. This is a harder failure than any single bug in prior passes, because it has two independent root causes stacked on top of each other.

**One thing genuinely improved underneath the outage:** `GoogleProvider` (`packages/infrastructure/ai/providers/google.py`) now correctly passes `api_key=settings.ai.google_api_key` — the "masked by an accident" bug from last pass is actually fixed. It just can't be proven live right now because nothing can start.

Also new this pass: a real `SafeCalculator` implementation replaced the old empty stub — it shipped with two crash bugs (an `ast.Num` removal in Python 3.14, and a `dataclass(slots=True)`/`__dict__` mismatch that broke every invocation), both now fixed and confirmed live, independent of the app-wide outage since the tool doesn't touch either broken import chain. Real pgvector-backed long-term memory code (`packages/memory/implementations/`) also landed but isn't wired correctly, and two large new zip archives (`packages.zip`, `packages/graph.zip` — full snapshots of `packages/` and `packages/graph/`) are now **committed to git history**, a worse recurrence of the junk-file pattern tracked in `docs/UNUSED_FILES.md`.

- Modules importing cleanly (last full sweep): **343 / 440 (77.9%)** — down sharply from 382/407 (93.9%) last pass. ~45 failures trace to bug #1 above, ~14 more to bug #2 and the same copy-paste mistake recurring in two more new, currently-unwired packages (`packages/middleware/`, `packages/planner/`).

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
| 1 — Foundation | 11 | 1 | 5 | 5 | 0 | **9.1%** ▼▼ |
| 2 — IAM | 7 | 0 | 2 | 0 | 5 | **0.0%** ▼ |
| 3 — Database | 12 | 8 | 0 | 0 | 4 | **66.7%** |
| 4 — LangChain | 10 | 1 | 0 | 6 | 3 | **10.0%** ▼▼ |
| 5 — LangGraph | 9 | 1 | 3 | 2 | 3 | **11.1%** ▼▼ |
| 6 — Session Management | 4 | 0 | 2 | 1 | 1 | **0.0%** ▼ |
| 7 — Memory | 5 | 0 | 1 | 0 | 4 | **0.0%** |
| 8 — Document Processing | 15 | 0 | 10 | 0 | 5 | **0.0%** |
| 9 — Production Retrieval ⭐ | 13 | 0 | 4 | 0 | 9 | **0.0%** |
| 10 — Tools | 6 | 1 | 3 | 0 | 2 | **16.7%** ▲ |
| 11 — Human in the Loop | 3 | 0 | 0 | 0 | 3 | **0.0%** |
| 12 — Background Jobs | 5 | 0 | 2 | 0 | 3 | **0.0%** ▼ |
| 13 — Production hardening | 5 | 1 | 2 | 0 | 2 | **20.0%** ▼ |
| 14 — APIs | 7 | 0 | 0 | 1 | 6 | **0.0%** ▼ |
| 15 — Testing | 4 | 0 | 0 | 0 | 4 | **0.0%** |
| 16 — Deployment | 3 | 0 | 3 | 0 | 0 | **0.0%** |
| **Total** | **119** | **13** | **37** | **15** | **54** | **10.9%** ▼ |

**Overall: 10.9% done · 31.1% partial · 12.6% broken · 45.4% pending** (13 / 37 / 15 / 54 out of 119 roadmap items) — updated post-audit after fixing the Calculator tool (see Broken → "`SafeCalculator` — fixed, two bugs found and closed"); Tools moved from 0.0% to 16.7%. This is effectively the same low point as the seventh pass (10.9% exactly), for a different reason: that pass had one root cause (a missing settings field); this one has two independent ones stacked together in `packages/graph/` and `packages/rag/`.

**Why nearly every phase dropped even though most of their own code didn't change:** last pass's milestone — Chat Models, Conditional Routing, Chat Sessions, the Chat API, Weather — all rested on one thing: a running app that could complete a real chat turn. That's gone this pass, not because any of those specific features regressed, but because two new bugs elsewhere (`packages/graph/nodes.py` vs `packages/graph/nodes/`, and copy-pasted `packages/rag/builders/`/`packages/rag/pipelines/` `__init__.py` files) block `packages.graph` and `packages.infrastructure.container.rag` from importing at all, which cascades to `packages.api.app`. Database and Production hardening's Configuration item are the only phases that held steady, because they don't depend on the broken import chain. Pending barely moved (55→54) — the one real addition (a substantive `SafeCalculator` tool) shipped broken on its very first non-trivial input.

---

## ✅ Done — properly implemented and proven

### Foundation
| Item | Evidence |
|---|---|
| Configuration & environment management | The only Foundation item unaffected by this pass's outage — `Settings()` constructs fine in isolation; this pass's two bugs live in `packages/graph/` and `packages/rag/`, not `packages/config/`. |

**Everything else in this phase regressed to Broken or Partial** — the app cannot import (`packages.api.app` fails via the `packages.graph` chain), so FastAPI application, exception handling, OpenAPI, health checks, and dependency injection are all **Broken** again; logging and tenant-context middleware are **Partial** (code presumably unaffected in isolation, but unprovable without a running app). CLI/Docker/Docker Compose unchanged, still Partial.

### Database
| Item | Evidence |
|---|---|
| Conversation & Message models, Knowledge Base / Document / Chunk models, Prompt Templates, Embeddings Metadata, Model Configurations, repository layer | All unaffected by this pass's two new bugs — none of these files touch `packages.graph` or `packages.rag.builders`/`packages.rag.pipelines`. |

**Not reflected in the 8-done tally above, but worth flagging:** `packages/rag/manager.py` (which several of these repositories are ultimately consumed through) itself fails to import this pass — see Broken. The models/tables are fine in isolation; the path that would exercise them through a live request is not.

### LangChain
| Item | Evidence |
|---|---|
| Document objects | Unaffected — `packages/rag/types.py` doesn't touch either of this pass's broken import chains. |

**Everything else regressed to Broken.** Chat Models and Gemini can no longer be proven live — `packages.rag.manager` (which `LLMManager` is ultimately reached through in the live chat path) fails to import via the `packages.rag.builders`/`packages.rag.pipelines` bug. **One genuine fix underneath, unprovable right now:** `GoogleProvider` (`packages/infrastructure/ai/providers/google.py`) now correctly passes `api_key=settings.ai.google_api_key` — the exact bug flagged last pass as "masked by an import-order accident" is actually resolved. It just can't be demonstrated live until the app can start. Embeddings, OpenAI, Anthropic, Groq: unchanged, still Broken/unverified.

### LangGraph
| Item | Evidence |
|---|---|
| GraphState | The `TypedDict` itself doesn't crash on import (Python doesn't enforce its type annotations at runtime) — but see Broken for a new internal inconsistency (`PlannerResult` now has two different, incompatible definitions that `state.py`/`router.py` reference inconsistently). |

**Regressed to Broken:** Nodes & package wiring, and Conditional routing / graph construction via DI. `packages/graph/nodes.py` (a file, still present) and a new `packages/graph/nodes/` (a directory, also present) now collide — Python resolves in favor of the directory, so the real `GraphNodes` class becomes unreachable. `packages/graph/builder.py` still imports the old `GraphNodes` and fails. This is the direct cause of the whole-app import failure. **Still Partial, unaffected:** Reducers, Checkpointing, Streaming.

### Session management
| Item | Evidence |
|---|---|
| No more duplicate user message (fix retained) | Code-level fix unaffected — but see below, this can no longer be proven live either. |

**Regressed to Broken:** Chat Sessions — the live, twice-confirmed full-turn proof from last pass is not reproducible this pass; `POST /api/v1/chat` cannot be reached at all since the app doesn't start.

### Tools
| Item | Evidence |
|---|---|
| Tool registry population, tool executor signature | Structurally unchanged — these describe wiring inside `packages/tools/`, which doesn't touch this pass's broken import chains directly. |
| **Calculator — new, fixed and confirmed live** | `packages/tools/builtin/calculator.py`'s `ast.Num` crash and a second, more severe `dataclass(slots=True)`/`__dict__` crash (found while fixing the first — it broke every invocation, not just complex ones) are both fixed. Confirmed live via direct tool calls: all arithmetic, all 14 functions, both constants, and error paths (division-by-zero, invalid constant, overflow) all work — including 21 of the tool's own 22 built-in test expressions. See Broken section for the full detail on both bugs. Doesn't depend on `packages.graph`/`packages.rag`, so this is genuinely proven working independent of the app-wide outage below. |

**Downgraded to Partial:** Web search and Weather — both tools' own code is unaffected and would likely still work if called directly/standalone, but the live, through-the-app proof from last pass depended on a running chat pipeline, which is gone this pass.

### Background jobs / Production
| Item | Evidence |
|---|---|
| Configuration management | Unaffected — `Settings()` itself still constructs fine. |

**Downgraded to Partial:** Redis connectivity, health monitoring — code unaffected, but the live proof (via the health route) is gone since the app can't start.

---

## 🔴 Broken — real code exists but currently fails

### The app cannot start — two independent, stacked causes

| Item | File(s) | What's wrong |
|---|---|---|
| **`packages/graph/nodes.py` (file) collides with `packages/graph/nodes/` (new directory)** | `packages/graph/nodes.py`, `packages/graph/nodes/__init__.py`, `packages/graph/builder.py:7` | The single highest-priority bug in the repo, and the direct cause of the app-wide import failure. An in-progress refactor added a new `packages/graph/nodes/` package (with `RetrieveNode`, `LLMNode`, a new planner, etc.) alongside the existing `packages/graph/nodes.py` file that defines the real, live `GraphNodes` class. Python resolves the name collision deterministically in favor of the package — confirmed empirically: `import packages.graph.nodes` returns the directory's near-empty `__init__.py` (`# init`), and `hasattr(it, 'GraphNodes')` is `False`. `packages/graph/builder.py:7` still does `from packages.graph.nodes import GraphNodes`, which now raises `ImportError`. Since `packages/graph/__init__.py` imports `GraphBuilder` at package level, **`import packages.graph` fails outright**, cascading into `packages/api/app.py` and everything downstream. The refactor is incomplete on both ends: `nodes.py`'s own `GraphNodes` already imports `from packages.graph.nodes.planner import GraphPlanner` (assuming the new package is live), but `builder.py` (the actual consumer) was never updated to use the new per-class nodes. Fix: either finish the migration (update `builder.py` to use the new node classes and delete `nodes.py`), or delete the new `nodes/` directory until the migration is ready — right now neither side works. |
| **`packages/rag/builders/__init__.py` and `packages/rag/pipelines/__init__.py` are copy-pasted from an unrelated package** | `packages/rag/builders/__init__.py`, `packages/rag/pipelines/__init__.py` | A second, independent cause of the same outage. Both new files are byte-for-byte `from .manager import MemoryManager` — but neither `packages/rag/builders/` nor `packages/rag/pipelines/` has a `manager.py` (that class lives in `packages/memory/manager.py`, an unrelated package). Confirmed broken directly: `ModuleNotFoundError: No module named 'packages.rag.builders.manager'`. This breaks `packages/infrastructure/container/rag.py` and `packages/rag/manager.py` independently of the `nodes.py` bug above — fixing one without the other still leaves the app unable to start. Fix: replace both files' contents with real `__init__.py`s (or make them empty) — they should not reference `MemoryManager` at all. |
| **The same copy-paste mistake, in two more new, currently-unwired packages** | `packages/middleware/__init__.py`, `packages/planner/__init__.py`, `packages/memory/implementations/__init__.py` | Same `from .manager import MemoryManager` template, same missing `manager.py`, in three more places from the same refactor batch. `packages/middleware/` and `packages/planner/` aren't imported by anything yet (confirmed via grep — no live impact today), but they're broken from the moment anyone tries to use them. `packages/memory/implementations/__init__.py`'s case is subtler: `packages/memory/manager.py` (one level up) *does* define `MemoryManager`, but the `implementations/__init__.py` is looking one level too deep for it — still `ModuleNotFoundError`. |
| **Two different `PlannerResult` classes, referenced inconsistently** | `packages/graph/planner.py` vs `packages/graph/nodes/planner.py` | A third instance of the same-name-different-class pattern already tracked in `docs/UNUSED_FILES.md` (`RetrievalPipeline`, `ChatService`). The old `planner.py` defines a `PlannerResult` with just `next_node: str`; the new `nodes/planner.py` defines a different one with `next_node`, `reason`, and a proper enum. `packages/graph/state.py` types `execution_plan` against the *old* one; `packages/graph/router.py` imports the `NextNode` enum from the *new* one. `TypedDict` doesn't enforce this at runtime, so it won't crash by itself — but it's a live source-of-truth split that will produce confusing bugs the moment real data flows through it. |

### Real, live bugs from last pass — one fixed, one unchanged (currently unprovable either way)

| Item | File(s) | What's wrong |
|---|---|---|
| **DB session provider shares one session across every request — still broken** | `packages/infrastructure/container/database.py` | The `session` provider is still `providers.Resource` instead of `providers.Factory`. Confirmed live: calling it twice returns the identical `AsyncSession` object. Fix: change back to `providers.Factory`. Currently the highest-severity *reachable* bug once the app-import failure above is fixed. |
| **`GoogleProvider` missing `api_key=` — fixed this pass** | `packages/infrastructure/ai/providers/google.py` | Confirmed: now correctly passes `api_key=settings.ai.google_api_key` to `ChatGoogleGenerativeAI(...)`. The bug flagged last pass as "masked by an unrelated `load_dotenv()` accident" is genuinely resolved — it just can't be demonstrated live right now since nothing can start. Move this to Done once the app-import bugs above are fixed and a live chat call reconfirms it. |

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

Two bugs block the app from starting at all — fix these first, before anything else on this list is even testable:

1. **Resolve the `packages/graph/nodes.py` vs `packages/graph/nodes/` collision.** Either finish the in-progress refactor (update `packages/graph/builder.py` to use the new per-class nodes in `packages/graph/nodes/`, then delete the old `nodes.py`) or delete the new `nodes/` directory until the migration is actually ready. Right now neither the old nor the new path works.
2. **Fix `packages/rag/builders/__init__.py` and `packages/rag/pipelines/__init__.py`** — both are copy-pasted `from .manager import MemoryManager`, which doesn't exist in either directory. Replace with real (or empty) `__init__.py` files. Independently blocks the app alongside item 1.
3. **Fix the same copy-paste mistake in `packages/middleware/__init__.py`, `packages/planner/__init__.py`, and `packages/memory/implementations/__init__.py`** — not yet wired into anything live, but broken the moment they are.

Once the app can start again:

4. **Revert the DB session `Factory`→`Resource` change** in `packages/infrastructure/container/database.py` — still shares one session across requests.
5. **Confirm `GoogleProvider`'s `api_key=` fix live** — the code fix landed this pass; just needs a real chat request to reconfirm now that the app can start.
6. **Reconcile the two `PlannerResult` classes** (`packages/graph/planner.py` vs `packages/graph/nodes/planner.py`) — pick one, delete the other, update `state.py`/`router.py` to agree.
7. **Fix `EmbeddingSettings` missing `provider`**, and `packages/knowledge/splitters/{pipeline,recursive,factory}.py`'s `DocumentSplitter`/`BaseSplitter` mismatch — both still unchanged from prior passes.
8. **Clean up the junk files, now committed to history, not just untracked** — `packages.zip`, `packages/graph.zip` (`git rm` both, add `.gitignore` rules), plus the rest of `docs/UNUSED_FILES.md`'s inventory (`packages/application/`, `sdk/` dead modules, `infrastructure/ai/factory.py`, `requirements.txt`, `graph.png`).
9. **Write an actual pytest suite.** Ten audit passes in, this is the strongest case yet: an in-progress refactor was committed mid-flight with two independent import-breaking bugs, and nothing caught it before it landed. A CI import-smoke-test alone (`python -c "from packages.api.app import app"`) would have caught both bugs in this pass in under a second.
10. **Restore the commit() calls in `packages/infrastructure/repositories/base.py`.**
11. **Wire up at least the Conversations router**, fix the Docker healthcheck path and Makefile paths, wire real JWT validation, and regenerate the Alembic "initial schema" migration properly.

**Fixed this pass:** `SafeCalculator`'s `ast.Num` crash and the `dataclass(slots=True)`/`__dict__` crash found alongside it — see Broken section for detail. One small, non-crashing gap remains (list-literal arguments to `sum`/`avg` aren't supported) but wasn't bundled into this fix.
