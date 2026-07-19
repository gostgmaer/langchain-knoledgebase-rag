# Build Status — MVP v1.0

Verified against [`docs/mvpRAG.md`](./mvpRAG.md) — that file is the **target roadmap** (what's in scope for v1.0/v1.1/v2.0 and why); this file is the **reality check** (what's actually built, working, broken, or missing right now). Read them as a pair: mvpRAG.md's ✅ marks mean "in v1.0 scope," not "done" — this document is where "done" gets verified.

Seventh audit pass, HEAD `5aac5a3`, working tree clean, re-verified 2026-07-20 by reading the actual current code, running a full import sweep, and attempting live `TestClient` smoke tests.

**Headline finding this pass — the app cannot start at all.** A new commit expanded `packages/domain/models/embedding.py` and `model_profile.py` to reference `settings.embedding.dimensions` at *class-definition time* (module import, not request time) — but `Settings` has no `embedding` field anywhere in `packages/config/`. Since `packages/api/lifespan.py` unconditionally does `import packages.domain.models`, and virtually the whole codebase transitively imports domain models, **`from packages.api.app import app` itself now raises `AttributeError` before any route, health check, or dependency-injection code runs.** This is a harder failure than last pass's "chat requests crash" — there is currently no ASGI app object to serve traffic at all. The two regressions from last pass are still present underneath this one (see Broken, below), but they're now moot: you can't reach them without an app to route through.

Also this pass: last pass's exception-handler wrong-import bug is genuinely fixed, and a large new `packages/knowledge/` subsystem landed targeting Document Processing/Production Retrieval — but it's orphaned (unwired anywhere) and internally broken on its own terms, in the same pattern as the earlier dead `packages/application/` layer.

- Modules importing cleanly (last full sweep): **254 / 401 (63.3%)** — down sharply from 309/331 (93.4%); the new `packages/knowledge/` package alone added 70 files, and the `settings.embedding` bug cascades into dozens of unrelated modules that transitively import domain models.

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
| 1 — Foundation | 11 | 2 | 4 | 5 | 0 | **18.2%** ▼▼ |
| 2 — IAM | 7 | 0 | 2 | 0 | 5 | **0.0%** ▼ |
| 3 — Database | 12 | 6 | 0 | 2 | 4 | **50.0%** ▼ |
| 4 — LangChain | 10 | 1 | 1 | 5 | 3 | **10.0%** |
| 5 — LangGraph | 9 | 2 | 3 | 1 | 3 | **22.2%** |
| 6 — Session Management | 4 | 0 | 2 | 1 | 1 | **0.0%** |
| 7 — Memory | 5 | 0 | 1 | 0 | 4 | **0.0%** |
| 8 — Document Processing | 15 | 0 | 10 | 0 | 5 | **0.0%** |
| 9 — Production Retrieval ⭐ | 13 | 0 | 4 | 0 | 9 | **0.0%** |
| 10 — Tools | 6 | 1 | 1 | 1 | 3 | **16.7%** |
| 11 — Human in the Loop | 3 | 0 | 0 | 0 | 3 | **0.0%** |
| 12 — Background Jobs | 5 | 0 | 2 | 0 | 3 | **0.0%** ▼ |
| 13 — Production hardening | 5 | 1 | 2 | 0 | 2 | **20.0%** ▼ |
| 14 — APIs | 7 | 0 | 0 | 1 | 6 | **0.0%** |
| 15 — Testing | 4 | 0 | 0 | 0 | 4 | **0.0%** |
| 16 — Deployment | 3 | 0 | 3 | 0 | 0 | **0.0%** |
| **Total** | **119** | **13** | **35** | **16** | **55** | **10.9%** ▼▼ |

**Overall: 10.9% done · 29.4% partial · 13.4% broken · 46.2% pending** (13 / 35 / 16 / 55 out of 119 roadmap items) — down from 21.0% done last pass, itself down from 25.2% the pass before.

**Why this pass is different from a normal regression:** last pass's `AISettings.top_p` bug broke chat requests specifically, while health checks, docs, and DI for other subsystems still worked. This pass's `settings.embedding.dimensions` bug breaks **app construction itself** — every phase whose "done" status depended on any live proof (health check, DI resolution, a running request) lost that proof simultaneously, because there is currently no way to start the process at all. That's why Foundation, IAM, Database, Background Jobs, and Production hardening all dropped this pass even though none of their own code changed — they were downgraded because the thing they depended on (a running app) no longer exists, not because they got worse individually. Pending stayed flat at 55/119 — the new `packages/knowledge/` subsystem is a real, substantial attempt at Document Processing/Production Retrieval, but it's non-functional and unwired, so it moves nothing from pending to partial; it just adds a second dead layer alongside the existing `packages/rag/` one.

---

## ✅ Done — properly implemented and proven

### Foundation
| Item | Evidence |
|---|---|
| Configuration & environment management | 12 typed `pydantic-settings` modules under `packages/config/` — `Settings()`/`get_settings()` itself still constructs without error in isolation (confirmed live, direct import). This is genuinely unaffected by this pass's app-breaking bug, which lives in `packages/domain/models/`, not `packages/config/`. |

**Everything else in this phase regressed to Broken or Partial this pass** — not because the code changed, but because the app can no longer start (see Broken → "app cannot import"), so none of it can be proven live anymore: FastAPI application, exception handling, OpenAPI, health checks, dependency injection are all now **Broken**; logging and tenant-context middleware are downgraded to **Partial** (the modules themselves likely still import fine in isolation, but "confirmed emitting logs/enforcing headers on real requests" is no longer provable without a running app).

### Database
| Item | Evidence |
|---|---|
| Conversation & Message models | `packages/domain/models/conversation.py` (190 lines), `message.py` (237 lines), citations modeled — these specific files are unaffected by this pass's bug |
| Knowledge Base / Document / Chunk models | SQLAlchemy models present under `packages/domain/models/` — unaffected |
| Prompt Templates | `prompt.py`, `prompt_version.py` — unaffected |
| Repository layer (11 classes, source) | `packages/infrastructure/repositories/` — the repository *classes themselves* are structurally unchanged |

**Regressed to Broken this pass:** "Embeddings Metadata" and "Model Configurations" — `packages/domain/models/embedding.py` and `model_profile.py` now reference `settings.embedding.dimensions` at class-definition time, but `Settings` has no `embedding` field anywhere. This raises `AttributeError` the moment `packages.domain.models` is imported — see Broken section for the full cascade. `model_profile.py` has two further bugs of its own on top of that (a wrong-submodule settings import reintroducing the exact bug just fixed in `exception_handlers.py`, and `from pgvector import Vector` — the plain value wrapper — instead of the SQLAlchemy column type `pgvector.sqlalchemy.Vector` that `embedding.py` correctly uses).
**Regressed to Broken:** "Repository layer, at runtime" — moot; there's no running app to prove it against, and the repositories backing the now-broken models can't even import.

### LangChain
| Item | Evidence |
|---|---|
| Document objects | `packages/rag/types.py` aliases `Document`/`Embeddings`/`VectorStore`, actually consumed by the RAG modules — unaffected by this pass's regression |

**Regressed to Broken this pass:** Chat Models and all four provider entries (Gemini/OpenAI/Anthropic/Groq) — see Broken section. The previous pass's live-verified Gemini completion no longer reproduces; `LLMManager.__init__` now crashes before any provider is even selected.

### LangGraph
| Item | Evidence |
|---|---|
| Nodes & package wiring | `packages/graph/nodes.py`'s `GraphNodes` — real `retrieve`/`llm`/`tool`/`summarize` methods; the code itself is unchanged and structurally sound |
| GraphState | `packages/graph/state.py` — `messages`, `documents`, `tools`, `user_id`, `conversation_id`, `thread_id`, `summary`, `metadata` fields all real |
| Checkpointing (in-memory) | `packages/graph/checkpoint.py`'s `GraphCheckpointFactory` wraps `MemorySaver`; constructor signature matches container wiring |

**Regressed to Broken this pass:** "Graph construction via DI" and "Conditional routing" — both were marked done last pass on the strength of a live, end-to-end agent-turn proof. That proof no longer reproduces: `container.graph.manager()` still resolves, but any actual `.invoke()`/`.ainvoke()` call crashes as soon as it needs an LLM (which is every real turn), for the same root cause as the LangChain regression above. The routing/node code itself hasn't changed — only its ability to actually run has.

### Session management
| Item | Evidence |
|---|---|
| No more duplicate user message (fix retained) | `ConversationManager` still does not double-append the user's `HumanMessage` — this earlier fix wasn't touched by this pass's changes |

**Regressed to Broken this pass:** "Chat sessions" (live end-to-end proof) — `POST /api/v1/chat` no longer completes a real turn; it crashes during dependency-injection of `agent_runtime`/`ai.manager` before `ConversationManager.chat()` even runs. The DB-persistence code itself is presumed unchanged and likely still correct in isolation, but it can no longer be proven live through the real HTTP path this pass — see Broken section.

### Tools
| Item | Evidence |
|---|---|
| Tool registry population | `packages/infrastructure/container/tools.py`'s `init_tool_manager(registry, executor)` calls `manager.register(get_weather)`, `.register(get_news)`, `.register(get_google_search)` — registry is now actually populated (previously nothing called `.register()`) |
| Tool executor signature | `packages/tools/executor.py`'s `ToolExecutor.execute(name, **kwargs)` → `tool.ainvoke(kwargs)` now matches exactly how `packages/graph/nodes.py`'s `GraphNodes.tool()` calls it (`self.context.tools.execute(tool_call["name"], **tool_call["args"])`) |
| Web search tool | `packages/tools/builtin/search.py` — real Serper integration, confirmed live (used successfully as a fallback when the weather tool 404'd) |
| Weather/news tool imports | `packages/tools/builtin/weather.py` / `news.py` now import `from packages.logging.logger import get_logger` — the old wrong `config.settings`/`shared.logger` paths from a different project are gone |

### Background jobs / Production
| Item | Evidence |
|---|---|
| Configuration management | Same as Foundation row above — `Settings()` itself still constructs fine; unaffected |

**Regressed to Partial this pass:** "Redis connectivity" — the client wrapper code is unchanged, but the live proof (`GET /health` returning healthy) is no longer obtainable since the app can't start.

---

## 🔴 Broken — real code exists but currently fails

| Item | File(s) | What's wrong |
|---|---|---|
| **`settings.embedding.dimensions` — the app cannot start at all** | `packages/domain/models/embedding.py:65`, `packages/domain/models/model_profile.py`, `packages/config/settings.py` | New this pass, and now the single highest-priority bug in the repo — worse than the `top_p` bug below, because it breaks *app construction itself*, not just one request path. `Embedding`'s column definition calls `Vector(settings.embedding.dimensions)` at class-definition time, but `Settings` has no `embedding` field anywhere in `packages/config/`. Since `packages/api/lifespan.py` unconditionally does `import packages.domain.models`, and nearly everything transitively imports domain models, **`from packages.api.app import app` now raises `AttributeError` before any route, health check, or DI code runs.** Confirmed live: there is no ASGI app object to test with `TestClient` at all. `model_profile.py` has two further bugs stacked on top: `from packages.config import settings` (the exact wrong-submodule-import bug just fixed in `exception_handlers.py`, reintroduced here) and `from pgvector import Vector` — the plain value wrapper, not the SQLAlchemy column type (`pgvector.sqlalchemy.Vector`) that `embedding.py` correctly uses instead. |
| `AISettings` missing `top_p`/`top_k` — still present, now moot | `packages/infrastructure/ai/config.py:38-39`, `packages/config/ai.py` | Unchanged since last pass, confirmed still live: `LLMManager()` still raises `AttributeError: 'AISettings' object has no attribute 'top_p'`. Three commits landed since this was flagged as the #1 priority and none touched `packages/config/ai.py`. Currently unreachable in practice since the app can't start regardless (see above), but will resurface as the next blocker the moment the `settings.embedding` bug is fixed. |
| Repository writes no longer commit — regression, unchanged | `packages/infrastructure/repositories/base.py` | Still only `flush()`s in `create()`/`update()`/`delete()`, no `commit()` — the fix from two passes ago that was reverted one pass ago is still reverted. |
| Orphaned `packages/application/` service layer — unwired, still broken on its own terms | `packages/application/services/{chat_service,conversation_service,message_service,runtime_service,history_services}.py` | Unchanged since last pass: nothing outside the package imports it; `ChatService._execute_runtime()` is still hardcoded to a fake response; the `datetime` module/class confusion and wrong repository import path are both still present. |
| **New — a second orphaned layer: `packages/knowledge/`** | `packages/knowledge/` (~70 files) | A large, ambitious new document-processing/retrieval subsystem (loaders, embeddings, processors, splitters, retrievers, an `IngestionPipeline`, a `KnowledgeManager` facade) landed this pass — and it's orphaned in exactly the same way `packages/application/` is: **nothing outside `packages/knowledge/` imports it** — not the DI container, not any router, not `GraphNodes.retrieve()`. It does not replace or conflict with the existing, still-live `packages/rag/` package; it just sits alongside it, unreachable. It's also internally broken: a naming collision between `packages/knowledge/schemas.py` (a file) and `packages/knowledge/schemas/` (a package) permanently shadows the package, making `schemas/chunk.py` and `schemas/embedding.py` unimportable; `loaders/factory.py` imports class names (`PDFDocumentLoader`, etc.) that don't match what the loader files actually define (`PDFLoader`, etc.); `IngestionPipeline` calls methods that don't exist on its own declared collaborators (`transformer.transform()` when the only method is `process()`; `splitter.split(tenant_id=..., content=...)` when the real signature takes one `SplitRequest` object; `embedding_manager.embed_documents(...)`/`embed_query(...)` when only `embed()` exists); `HybridRetriever` and the pgvector backend's `mmr_search()` are both explicit `NotImplementedError` stubs; and the embedding provider classes (`google.py`/`openai.py`/`ollama.py`) read settings paths that don't exist (`settings.embedding.model`, `settings.openai.api_key`, `settings.ollama.base_url` — none are real fields). Reads as generated scaffolding that was never run once, not a working implementation. |
| Exception handler — the wrong-import bug is fixed; the UnicodeEncodeError finding is more nuanced than reported last pass | `packages/api/exception_handlers.py` | **Fixed:** now correctly `from packages.config.loader import settings` — `settings.app.debug` resolves cleanly, no more `AttributeError`. **Correction to last pass:** under the real app's actual logging configuration (`configure_logger()`, called from `lifespan.py`), a `UnicodeEncodeError` from logging a unicode character does *not* produce an empty 500 body as previously reported — Python's stdlib logging `Handler.handleError()` catches that encode failure internally and just prints noisy `--- Logging error ---` output to stderr; the client still gets a proper JSON error envelope. The "every 500 returns empty body" claim from last pass was an artifact of testing the handler in isolation, without `lifespan()` having run first. This is currently moot either way, since the app can't start at all (see the top of this table). |
| Weather tool functionally broken | `packages/tools/builtin/weather.py:55-70`, `.env:118` | Unchanged — `OPENWEATHER_BASE_URL` still missing `/weather`. |
| Dead orphaned provider factory (old) | `packages/infrastructure/ai/factory.py` | Unchanged — still imports provider classes that no longer exist in `.registry`; superseded by `infrastructure/ai/providers/factory.py`, should just be deleted. |
| Stale `AgentState` import | `packages/conversation/store.py`, `packages/conversation/memory_store.py`, `packages/application/application.py` | Unchanged. |
| Upload SDK wrong import | `sdk/upload/client.py:5` | Unchanged. |
| Notification SDK missing dependency | `sdk/notification/` (5 modules) | Unchanged. |
| `sdk/common/models.py` | `sdk/common/models.py` | Unchanged — `NameError: name 'Pagination' is not defined`. |

**Previously broken, now fixed:** the `GraphVisualizer.save_png()` regression and the exception handler's wrong-submodule-import bug are both genuinely resolved.

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

**Practical impact:** anyone can call any `/api/v1/*` route by sending any `X-Tenant-ID` header value — there is no verification that the caller is actually that tenant. This is the single largest gap between "MVP" and anything safe to expose beyond localhost. (Tenant/organization context itself was previously "Done" on the strength of live 400-without-header/200-with-header proof; downgraded to Partial this pass only because that proof is currently unobtainable — the app can't start — not because the middleware code changed.)

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

**Practical impact:** the entire HTTP-reachable chat surface is one endpoint — send a message into an existing conversation, non-streaming, with no way to create that conversation, list its history, or delete it over HTTP. **And that one endpoint is currently broken anyway** — see Broken → `AISettings.top_p`/`top_k` — so as of this pass, the live-reachable API surface is effectively just `GET /api/v1/health`.

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

### 14. `PromptContext` reshaped (uncommitted) — richer fields added, but still entirely ignored
Uncommitted changes to `packages/infrastructure/ai/prompts/context.py` drop the old `tools: list[str] | None` field, convert `history`/`memories`/`documents` to `field(default_factory=list)`, and add a new `system_prompt: str | None`. This doesn't break anything — `packages/infrastructure/ai/prompts/builder.py`'s `PromptBuilder.build()` never read `context.tools` or any of the other fields to begin with; it hardcodes a system message plus the raw user message only. But it does underscore that `PromptContext`'s richer fields (history, memories, documents, system_prompt) are populated by whatever calls into it and then **entirely discarded** — conversation history and retrieved documents never actually reach the LLM prompt today, regardless of how much of the pipeline in front of them works.

---

## Suggested next priorities (roughly in order)

1. **Fix `settings.embedding.dimensions`** (`packages/domain/models/embedding.py:65`, `model_profile.py`) — now the single highest-priority item in the repo; the app cannot start at all until this is fixed. Either add an `embedding` settings group to `Settings` (with a `dimensions` field), or change these two files to read the dimension from wherever it's actually meant to come from (e.g. a column argument at model-instantiation time instead of module-import time). Also fix `model_profile.py`'s two piggybacking bugs while in there: `from packages.config import settings` → `from packages.config.loader import settings`, and `from pgvector import Vector` → `from pgvector.sqlalchemy import Vector`.
2. **Fix `AISettings` missing `top_p`/`top_k`** (`packages/config/ai.py`) — still unresolved after three more commits, and it's the next blocker in line the moment #1 is fixed. Two-line fix (add `top_p`/`top_k` fields matching the values already sitting unused in `.env`).
3. **Restore the commit() calls removed from `packages/infrastructure/repositories/base.py`** — still reverted since two passes ago; writes on the live chat path are flushed but never durably committed.
4. **Decide the fate of `packages/application/` AND `packages/knowledge/`** — both are large, unwired, internally-broken parallel implementations now (the same pattern, twice). Either wire one/both in for real, or delete them before a third one appears. `packages/knowledge/` in particular has a real, coherent architecture on paper (loaders→processors→splitters→embeddings→retrievers) — if the intent is to eventually replace `packages/rag/` with it, that's a reasonable direction, but it needs its internal method signatures reconciled with its own collaborators before it does anything at all.
5. **Delete `infrastructure/ai/factory.py` and the unused `LLMRegistry`** — both superseded by `infrastructure/ai/providers/`.
6. **Fix the Docker healthcheck path** (`/health` → `/api/v1/health`) and either populate `docker-compose.dev.yml` or remove the `make dev` target that expects it.
7. **Fix the Makefile's `docker/compose/` paths** — that directory doesn't exist; the real compose files are at the repo root.
8. **Fix `docker/scripts/wait-for-db.py`'s corrupted `echo`/`exec` lines** before it's ever actually invoked.
9. **Wire real JWT validation** behind the existing tenant-context middleware, and add CORS middleware (gap #2).
10. **Regenerate the Alembic "initial schema" migration properly** — the current one only does an `alter_column` and would fail against a genuinely empty database.
11. **Wire up at least the Conversations router** — there's still no HTTP-reachable way to create a conversation.
12. **Write an actual pytest suite** — zero automated regression protection anywhere in the repo. This pass makes the case starkest yet: three consecutive passes have each found the app in a *worse* runtime state than the one before, entirely from changes nobody ran once before committing.
13. **Fix the vectorstore backend silent-`None` fallthrough** for faiss/qdrant (gap #8).
14. **Write a real README** — setup steps, required env vars, how to run the server locally.
15. **Close the weather tool's `httpx.AsyncClient`** on shutdown, and fix `OPENWEATHER_BASE_URL`/`UPLOAD_SERVICE_URL` in the real `.env`.
