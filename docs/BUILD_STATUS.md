# Build Status — MVP v1.0

Verified against [`docs/mvpRAG.md`](./mvpRAG.md) — that file is the **target roadmap** (what's in scope for v1.0/v1.1/v2.0 and why); this file is the **reality check** (what's actually built, working, broken, or missing right now). Read them as a pair: mvpRAG.md's ✅ marks mean "in v1.0 scope," not "done" — this document is where "done" gets verified.

Fifth audit pass, HEAD `d48ce50` + 1 uncommitted file (`packages/graph/manager.py`), re-verified 2026-07-19 by reading the actual current code (not commit messages) and cross-checking against prior runtime testing (`TestClient` requests, direct `container.graph.manager().invoke()` calls against live Gemini/Serper/OpenWeather APIs, and a full import sweep of `packages/`).

- Modules importing cleanly (last full sweep): **266 / 285 (93.3%)**

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
| 1 — Foundation | 11 | 8 | 1 | 0 | 2 | **72.7%** |
| 2 — IAM | 7 | 2 | 0 | 0 | 5 | **28.6%** |
| 3 — Database | 12 | 8 | 0 | 0 | 4 | **66.7%** |
| 4 — LangChain | 10 | 3 | 4 | 0 | 3 | **30.0%** |
| 5 — LangGraph | 9 | 3 | 3 | 0 | 3 | **33.3%** |
| 6 — Session Management | 4 | 1 | 2 | 0 | 1 | **25.0%** |
| 7 — Memory | 5 | 0 | 1 | 0 | 4 | **0.0%** |
| 8 — Document Processing | 15 | 0 | 10 | 0 | 5 | **0.0%** |
| 9 — Production Retrieval ⭐ | 13 | 0 | 4 | 0 | 9 | **0.0%** |
| 10 — Tools | 6 | 1 | 1 | 1 | 3 | **16.7%** |
| 11 — Human in the Loop | 3 | 0 | 0 | 0 | 3 | **0.0%** |
| 12 — Background Jobs | 5 | 1 | 0 | 0 | 4 | **20.0%** |
| 13 — Production hardening | 5 | 3 | 0 | 0 | 2 | **60.0%** |
| 14 — APIs | 7 | 0 | 1 | 0 | 6 | **0.0%** |
| 15 — Testing | 4 | 0 | 0 | 0 | 4 | **0.0%** |
| 16 — Deployment | 3 | 0 | 0 | 0 | 3 | **0.0%** |
| **Total** | **119** | **30** | **27** | **1** | **61** | **25.2%** |

**Overall: 25.2% done · 22.7% partial · 0.8% broken · 51.3% pending** (30 / 27 / 1 / 61 out of 119 roadmap items).

A quick way to read this: **51% of the roadmap hasn't been started at all**, another **23% has real code behind it that isn't proven to work end to end yet**, and only about a **quarter is both built and verified**. The phases dragging the average down hardest are the three sitting at 0%: Memory (long-term memory entirely unbuilt), Document Processing (real pipeline shape, zero live verification), and Production Retrieval — the roadmap's own starred centerpiece. IAM (28.6%) and Tools (16.7%) are the next biggest gaps, both for the same reason: what's "done" is real but only covers a fraction of what the phase actually promises (tenant-header presence without JWT verification; one working tool out of six).

---

## ✅ Done — properly implemented and proven

### Foundation
| Item | Evidence |
|---|---|
| Configuration & environment management | 12 typed `pydantic-settings` modules under `packages/config/` (`app.py`, `api.py`, `db.py`, `redis.py`, `security.py`, `storage.py`, `queue.py`, `features.py`, `ai.py`, `iam.py`, `upload_service.py`, `notification.py`), env-backed via `.env` |
| FastAPI application | `packages/api/app.py` — real app factory + `lifespan` (`packages/api/lifespan.py`), not a placeholder |
| Exception handling (structure) | `packages/api/exception_handlers.py` — maps `RequestValidationError` → 422, `HTTPException` → passthrough status, unhandled `Exception` → 500, all through one `ErrorResponse` envelope (`packages/api/responses.py`) |
| OpenAPI | `/docs`, `/redoc`, `/openapi.json` live with real title/description/version, per-route summaries |
| Health checks | `packages/api/routers/health.py` — genuinely checks Postgres and Redis connectivity, confirmed live returning `{"database":"healthy","redis":"healthy"}` against real services, not a static "OK" |
| Dependency injection | `packages/infrastructure/container/*.py` — `ApplicationContainer`'s `ai`, `graph`, `memory`, `database`, and `tools` branches all construct without error (confirmed by resolving `container.graph.manager()` directly) |
| Logging | `packages/shared/logging.py` (structlog) + `packages/api/middleware/request_id.py` — confirmed emitting structured logs with request IDs on real requests |
| Tenant-context middleware | `packages/api/middleware/tenant.py` (63 lines) + `packages/api/security.py`'s `get_tenant_id` dependency — reads `X-Tenant-ID`/`X-Organization-ID` headers into `request.state`, enforced on every `/api/v1/*` route via `Depends(get_tenant_id)` in `packages/api/routers/__init__.py`. **Caveat:** presence only, no verification — see Pending → IAM |

### Database
| Item | Evidence |
|---|---|
| Conversation & Message models | `packages/domain/models/conversation.py` (190 lines), `message.py` (237 lines), citations modeled |
| Knowledge Base / Document / Chunk / Embeddings models | 4 SQLAlchemy models present under `packages/domain/models/` |
| Prompt Templates / Model Configurations | `prompt.py`, `prompt_version.py`, `model_profile.py` |
| Repository layer (11 classes) | `packages/infrastructure/repositories/` — import cleanly, circular import between `knowledge_base.py`/`agent_knowledge_base.py` resolved with `TYPE_CHECKING` guards |
| Repository layer, at runtime | `packages/infrastructure/database/session.py`'s `create_session()` returns a real `AsyncSession` (not the raw `async_sessionmaker`); `packages/infrastructure/repositories/base.py`'s `create/update/delete/delete_by_id` now `await self.session.commit()` after the write, not just `flush()`. Proven live: a chat request against a nonexistent conversation ID returns a clean 404, not a crash |

### LangChain
| Item | Evidence |
|---|---|
| Chat models | `packages/infrastructure/ai/manager.py`'s `LLMManager` + `registry.py`'s `LLMRegistry.create()` (static method, reads `packages.config.loader.settings`) — both the direct call path and `container.ai.manager()` through DI now work. Verified live: real Gemini completion (`gemini-3.1-flash-lite`, real token usage) |
| Provider wiring | Gemini, OpenAI, Anthropic, Groq all wired in `LLMRegistry.create()` (only Gemini exercised live so far) |
| Document objects | `packages/rag/types.py` aliases `Document`/`Embeddings`/`VectorStore`, actually consumed by the RAG modules |

### LangGraph
| Item | Evidence |
|---|---|
| Graph construction via DI | `container.graph.manager()` resolves cleanly (previously `TypeError: LLMRegistry() takes no arguments`) |
| Nodes | `packages/graph/nodes.py`'s `GraphNodes` — real `retrieve`/`llm`/`tool`/`summarize` methods |
| Conditional routing | `packages/graph/router.py`'s `GraphRouter` — planner routes messages through `retrieve`/`tool`/`llm` branches; proven live in a full agent turn ending in a tool-call loop back to a final answer |
| GraphState | `packages/graph/state.py` — `messages`, `documents`, `tools`, `user_id`, `conversation_id`, `thread_id`, `summary`, `metadata`, all populated in the live run above |
| Checkpointing (in-memory) | `packages/graph/checkpoint.py`'s `GraphCheckpointFactory` wraps `MemorySaver`; constructor signature now matches container wiring (previously `CheckpointFactory.__init__() got an unexpected keyword argument 'settings'`) |
| Agent runtime | New `packages/agent/` package (`context.py`, `prompt.py`, `runtime.py`, `response.py`) — `AgentRuntime` wired into `ApplicationContainer` (`llm=ai.manager, prompt_builder=prompt_builder, tools=tools.manager`), consumed by `NodeContext.runtime`, called from `GraphNodes.llm()` |

### Session management
| Item | Evidence |
|---|---|
| Chat sessions | `packages/conversation/manager.py`'s `ConversationManager` — DB-backed persistence proven live end to end through `POST /api/v1/chat` |
| No more duplicate user message | `ConversationManager` no longer double-appends the user's `HumanMessage` after `ConversationContextBuilder.build()` already loaded it from the DB via `MessageRepository` — previously the same message was sent to the LLM twice per turn |

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
| Redis connectivity | `packages/infrastructure/redis/` client wrapper + health check — confirmed live and healthy via the real `/health` endpoint |
| Configuration management | Same as Foundation row above — solid |

---

## 🔴 Broken — real code exists but currently fails

| Item | File(s) | What's wrong |
|---|---|---|
| Exception handler leaks tracebacks | `packages/api/exception_handlers.py:41-49` | `unhandled_exception_handler` builds `message=f"Internal server error. Traceback: {tb}"` and returns it verbatim in the 500 response body. This is now **committed** (part of `d48ce50`), not just a working-tree draft — an information-disclosure risk that should be gated behind a debug flag before any external exposure. |
| Weather tool functionally broken | `packages/tools/builtin/weather.py:55-70`, `.env:118` | `OPENWEATHER_BASE_URL=https://api.openweathermap.org/data/2.5` is missing the `/weather` path segment, so `url = os.getenv("OPENWEATHER_BASE_URL")` is called directly with no endpoint appended. Every real call 404s, and the `except httpx.HTTPStatusError` branch (line 84-85) silently reports this as `"City '<x>' not found."` instead of surfacing the real config error. Confirmed live: agent tried the tool twice, got "not found" both times, then correctly fell back to `get_google_search`. |
| Dead orphaned provider factory | `packages/infrastructure/ai/factory.py` | Imports `AnthropicProvider`, `GoogleProvider`, `GroqProvider`, `OpenAIProvider` from `.registry`, but `registry.py` was refactored to the static `LLMRegistry` and no longer defines those classes → `ImportError` on import. Confirmed unused anywhere else in the app via grep — should be deleted rather than fixed. |
| Stale `AgentState` import | `packages/conversation/store.py`, `packages/conversation/memory_store.py`, `packages/application/application.py` | All three still `from packages.graph.state import AgentState`, which was renamed to `GraphState` during the LangGraph rewrite. Not on the live chat path (dead code), but will raise `ImportError` if anything ever imports them. |
| Upload SDK wrong import | `sdk/upload/client.py:5` | `from packages.config.upload import UploadSettings` — the real file is `packages/config/upload_service.py`, the real class is `UploadServiceSettings`. Breaks 8 modules under `sdk/upload/`. |
| Notification SDK missing dependency | `sdk/notification/` (5 modules) | Requires the `email-validator` extra, which isn't installed in the venv. |
| `sdk/common/models.py` | `sdk/common/models.py` | `NameError: name 'Pagination' is not defined` — the file declares bare names (`Pagination`, `Page`, `Metadata`, `ErrorResponse`, `HealthResponse`) with no actual class definitions behind them. |

**Previously broken, now fixed:** the `GraphVisualizer.save_png()` regression (uncommented network call to mermaid.ink + Windows console crash) that briefly reintroduced a 500 on `POST /api/v1/chat` has been **re-commented out** in `packages/graph/manager.py:16` (currently an uncommitted one-line change — remember to commit it). The correct long-term pattern already exists in `packages/api/lifespan.py:34-39`, which wraps the same call in a `try/except` with the comment *"Rendering uses the remote mermaid.ink API — never block startup on it"* — but that call is also commented out there, so nothing currently generates `graph.png` automatically, which is the safe default.

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

**Practical impact:** anyone can call any `/api/v1/*` route by sending any `X-Tenant-ID` header value — there is no verification that the caller is actually that tenant. This is the single largest gap between "MVP" and anything safe to expose beyond localhost.

### Database (Phase 3)
| Item | Status |
|---|---|
| Migrations | `packages/infrastructure/migrations/` is a **completely empty directory** (no files, not even `__init__.py`). `alembic>=1.18.5` is a declared dependency but there's no `alembic.ini` or `alembic/` directory anywhere. Schema is created only via `Base.metadata.create_all` in `lifespan.py:46` |
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

### Production Retrieval (Phase 9 — the roadmap's ⭐ centerpiece)
| Item | Status |
|---|---|
| Query classification, rewriting, expansion | No code found |
| Hybrid / BM25 search, metadata filtering, re-ranking | Not implemented |
| Context building, prompt construction for retrieval | Not implemented |
| Citation generation | `message_citation.py` DB model exists but nothing populates it |

This is still the phase furthest from its own ambition in the roadmap — the star marks it as the production centerpiece, and it has the least real retrieval logic behind it of any phase.

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
| Queue | `arq` is a declared dependency; `packages/infrastructure/queue/__init__.py` is a **1-line stub** |
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

**Practical impact:** the entire HTTP-reachable chat surface is one endpoint — send a message into an existing conversation, non-streaming, with no way to create that conversation, list its history, or delete it over HTTP. The testing CLI added in commit `72f2b8f` works around the missing creation route with a hardcoded dummy conversation UUID and a comment admitting "you may need to seed the database with this conversation ID manually."

### Testing (Phase 15)
| Item | Status |
|---|---|
| Unit / integration / LangGraph workflow / API tests | `tests/` contains only `__init__.py` and `test_llm.py` (24 lines). `test_llm.py` is a manual `asyncio.run(...)` + `print(...)` smoke script — **zero `assert` statements in the entire repo**, despite `pytest`, `pytest-asyncio`, and `pytest-cov` all being declared dependencies in `pyproject.toml` |

### Deployment (Phase 16)
| Item | Status |
|---|---|
| Dockerfile | Does not exist anywhere in the repo |
| docker-compose.yml | Exists but is **0 bytes** |
| Production configuration | Not implemented |

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

### 5. Async session handling — no per-request close, no rollback on failure
This is the one most likely to cause a real production incident:
- `packages/infrastructure/container/database.py:25-28` wires `session = providers.Factory(create_session, ...)`, and `packages/api/dependencies.py`'s `get_db_session` (lines 31-35) just returns that session directly — `Factory` providers have no teardown hook, so **there is no code path that closes a request's DB session** after the request finishes.
- `packages/infrastructure/repositories/base.py`'s `create()` (30-38), `update()` (92-99), and `delete()` (105-110) call `session.flush()`/`commit()` with **no `try/except`** — if a write raises (e.g. `IntegrityError`), the session is left in a failed-transaction state and, per the point above, is never closed either.
- The codebase already has the correct pattern: `packages/infrastructure/database/transaction.py`'s `UnitOfWork.__aexit__` (lines 17-27) does rollback-on-exception and always closes the session — but it's wired as a separate, unused `uow` provider (`database.py:30-33`). The live chat path goes through `get_db_session`/repositories directly, not `UnitOfWork`, so the safe pattern exists in the codebase but isn't actually used where it matters.

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

### 13. `.env` / `.env.example` are largely a stale template from a different project
Checked every `Field(alias=...)` in `packages/config/*.py` against both `.env` and `.env.example`. Verdict: **`.env.example` is a near-verbatim copy of `langgraph-cli-chat-agent`'s env template** (SQLite paths, a single `LLM_PROVIDER` switch, `CLI_THEME`, `AGENT_MAX_ITERATIONS` — none of which correspond to anything in this project's actual settings classes) — it does not reflect this codebase and would actively mislead anyone onboarding from it. The real `.env` is the same stale template with a handful of genuinely-used keys appended at the bottom.

**Wrong value:**
- `UPLOAD_SERVICE_URL=https://api.smith.langchain.com` (`.env:174`) — this is LangSmith's endpoint, not a real upload service. Looks like a copy-paste error; `UploadServiceSettings.base_url` (`packages/config/upload_service.py:15-18`) has no default, so it happily accepts this as "valid" (it's a well-formed URL) and would call the wrong host if the Upload SDK is ever exercised.

**Name mismatches — value in `.env` is silently ignored, setting falls back to its Python default:**
| `.env` has | Settings class expects | File |
|---|---|---|
| `VECTOR_STORE` | `VECTOR_STORE_BACKEND` | `packages/config/rag.py:17` |
| `ENABLE_SEARCH_TOOL`, `ENABLE_WEATHER_TOOL`, `ENABLE_NEWS_TOOL`, `ENABLE_CALCULATOR_TOOL` | `ENABLE_WEB_SEARCH`, `ENABLE_WEATHER`, `ENABLE_NEWS`, `ENABLE_CALCULATOR` (plus `ENABLE_TOOLS`, `ENABLE_MEMORY`, `ENABLE_STREAMING`, `ENABLE_RERANKING`, `ENABLE_QUERY_REWRITE`, none of which are set in `.env` at all) | `packages/config/features.py` |
| `UPLOAD_DIR` | `StorageSettings` has no matching alias at all (its fields are unaliased, matched by bare name — `UPLOAD_DIRECTORY`, `TEMP_DIRECTORY`, `MAX_FILE_SIZE`) | `packages/config/storage.py` |
| `LOG_FORMAT` | Not read anywhere — `LoggingSettings` only defines `LOG_LEVEL`/`LOG_JSON` | `packages/config/logging.py` |

**Practical impact:** every feature flag (`ENABLE_*`) is currently unconfigurable via `.env` — they're all silently pinned to their hardcoded Python defaults (mostly `True`) no matter what the file says. Same for the vector store backend selection.

**Placeholder secrets that would fail if actually used:**
- `IAM_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxx` and `IAM_INTROSPECTION_API_KEY=xxxxxxxxxxxxxxxxxxxx` (`.env:182,185`) — harmless today only because nothing calls the IAM SDK yet (see Phase 2). Worth replacing before JWT validation is wired up.

**A real startup-crash risk if this ever regresses:** `packages/config/loader.py:19-34`'s `get_settings()` eagerly instantiates `IAMSettings()` at **import time** (`settings = get_settings()` runs on module load). `IAMSettings` (`packages/config/iam.py`) requires `IAM_BASE_URL`/`IAM_CLIENT_ID`/`IAM_CLIENT_SECRET`/`IAM_INTROSPECTION_API_KEY` with **no defaults** — if any of those four were ever removed from `.env`, the entire app would fail to import before it even starts, not just fail on first use.

**Roughly half the file (~50 lines) is pure dead weight**, unused by any current settings class: `LLM_MODEL`, `TOP_P`/`TOP_K`, `OLLAMA_BASE_URL`, `CHECKPOINT_DB_PATH`/`SESSION_DB_PATH`/`SUMMARY_DB_PATH`, `CHROMA_PERSIST_DIR`, `FAISS_INDEX_PATH`, `QDRANT_URL`/`QDRANT_API_KEY`, `POSTGRES_HOST`/`PORT`/`DB`/`USER`/`PASSWORD` (dead since `DATABASE_URL` is the one connection string actually used), `RETRIEVAL_TOP_K`/`RETRIEVAL_STRATEGY`, `SEARCH_PROVIDER`, `HTTP_TIMEOUT`/`MAX_RETRIES`/`RETRY_DELAY`/`USER_AGENT`, `CLI_THEME`/`CLI_STREAMING`/`CLI_SHOW_TOOL_CALLS`/`CLI_SHOW_THINKING`, `LANGCHAIN_TRACING_V2`/`LANGCHAIN_ENDPOINT`/`LANGCHAIN_API_KEY`/`LANGCHAIN_PROJECT`, `SESSION_TTL_HOURS`/`MAX_SESSIONS`, `AGENT_MAX_ITERATIONS`/`AGENT_MAX_TOOL_CALLS`/`AGENT_TIMEOUT`.

**What is genuinely correct and matches:** `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `QUEUE_PREFIX`, `GOOGLE_API_KEY`/`OPENAI_API_KEY`/`ANTHROPIC_API_KEY`/`GROQ_API_KEY`, `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL`, `CHUNK_SIZE`/`CHUNK_OVERLAP`, `SERPER_API_KEY`/`TAVILY_API_KEY`/`NEWSAPI_API_KEY`, `OPENWEATHER_API_KEY` (though its `_BASE_URL` sibling has the separate `/weather`-path bug from gap #2 above), and all seven `IAM_*` vars (present, two are placeholders).

---

## Suggested next priorities (roughly in order)

1. **Commit the `GraphVisualizer` fix** in `packages/graph/manager.py` — it's currently just an uncommitted working-tree change.
2. **Gate the exception-handler traceback leak** behind a debug flag (`packages/api/exception_handlers.py:48`) — this is committed and currently ships raw tracebacks to any caller who triggers a 500, including from the missing-API-key failure mode in gap #9 below.
3. **Fix the DB session lifecycle** (gap #5) — either switch the live chat path to `UnitOfWork`, or add explicit close/rollback to `get_db_session`. This is the highest-severity gap found this pass: unbounded session leakage under any sustained load.
4. **Fix `OPENWEATHER_BASE_URL`** in `.env` — append `/weather` (or the correct OpenWeatherMap endpoint path).
5. **Wire real JWT validation** behind the existing tenant-context middleware, and add CORS middleware (gap #2) — right now tenant identity is trusted, not verified, and there's no CORS policy or docs-exposure gating at all.
6. **Generate an initial Alembic migration** from the existing 15+ ORM models — schema currently only exists via `create_all`, with no upgrade/rollback story.
7. **Wire up at least the Conversations router** — right now there's no HTTP-reachable way to create a conversation; everything downstream of chat depends on a hand-seeded UUID.
8. **Write an actual pytest suite** — there is currently zero automated regression protection anywhere in the repo.
9. **Fix the vectorstore backend env-var mismatch and add an explicit error for unimplemented backends** (gap #8) — `VECTOR_STORE` vs `VECTOR_STORE_BACKEND`, and the silent-`None` fallthrough for faiss/qdrant.
10. **Write a real README** — setup steps, required env vars, and how to run the server locally.
11. **Rewrite `.env.example` from scratch against the actual `packages/config/*.py` settings classes** (gap #13) — the current one is a different project's template and will actively mislead anyone onboarding from it. Fix the `ENABLE_*` feature-flag name mismatches and `UPLOAD_SERVICE_URL` while at it.
12. **Delete the dead code**: `infrastructure/ai/factory.py` (orphaned `LLMFactory`), and the stale `AgentState` imports in `conversation/store.py` / `memory_store.py` / `application/application.py`.
13. **Close the weather tool's `httpx.AsyncClient`** on shutdown, or switch it to the same per-call pattern `news.py`/`search.py` already use.
