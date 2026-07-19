# Build Status — MVP v1.0

Verified against [`docs/mvpRAG.md`](./mvpRAG.md) — that file is the **target roadmap** (what's in scope for v1.0/v1.1/v2.0 and why); this file is the **reality check** (what's actually built, working, broken, or missing right now). Read them as a pair: mvpRAG.md's ✅ marks mean "in v1.0 scope," not "done" — this document is where "done" gets verified.

Sixth audit pass, HEAD `4f4e5db` + 6 uncommitted files (`packages/application/services/runtime_service.py`, `packages/infrastructure/ai/prompts/context.py`, `packages/api/dependencies.py`, `packages/api/exception_handlers.py`, `packages/infrastructure/repositories/unit_of_work.py`, and new untracked `packages/application/services/history_services.py`), re-verified 2026-07-19 by reading the actual current code, running a full import sweep, and live `TestClient` smoke tests (including `raise_server_exceptions=True` to find root causes hidden behind the exception handler).

**Headline finding this pass:** four real new subsystems landed (Docker, Alembic migrations, a background worker process, a rebuilt AI provider architecture) — but the same batch of commits also introduced a regression that currently **breaks every chat request**: `LLMManager.__init__` now reads `settings.ai.top_p`/`settings.ai.top_k`, but `AISettings` (`packages/config/ai.py`) defines no such fields. This crashes during dependency-injection, before the route handler even runs, undoing the "it works end-to-end" proof from the previous pass. Net effect: real infrastructure progress, but overall verified completion is *down* this pass, not up — see the phase table below.

- Modules importing cleanly (last full sweep): **309 / 331 (93.4%)**

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
| 1 — Foundation | 11 | 7 | 3 | 1 | 0 | **63.6%** ▼ |
| 2 — IAM | 7 | 2 | 0 | 0 | 5 | **28.6%** |
| 3 — Database | 12 | 8 | 0 | 0 | 4 | **66.7%** |
| 4 — LangChain | 10 | 1 | 1 | 5 | 3 | **10.0%** ▼▼ |
| 5 — LangGraph | 9 | 2 | 3 | 1 | 3 | **22.2%** ▼ |
| 6 — Session Management | 4 | 0 | 2 | 1 | 1 | **0.0%** ▼ |
| 7 — Memory | 5 | 0 | 1 | 0 | 4 | **0.0%** |
| 8 — Document Processing | 15 | 0 | 10 | 0 | 5 | **0.0%** |
| 9 — Production Retrieval ⭐ | 13 | 0 | 4 | 0 | 9 | **0.0%** |
| 10 — Tools | 6 | 1 | 1 | 1 | 3 | **16.7%** |
| 11 — Human in the Loop | 3 | 0 | 0 | 0 | 3 | **0.0%** |
| 12 — Background Jobs | 5 | 1 | 1 | 0 | 3 | **20.0%** |
| 13 — Production hardening | 5 | 3 | 0 | 0 | 2 | **60.0%** |
| 14 — APIs | 7 | 0 | 0 | 1 | 6 | **0.0%** |
| 15 — Testing | 4 | 0 | 0 | 0 | 4 | **0.0%** |
| 16 — Deployment | 3 | 0 | 3 | 0 | 0 | **0.0%** ▲ |
| **Total** | **119** | **25** | **29** | **10** | **55** | **21.0%** ▼ |

**Overall: 21.0% done · 24.4% partial · 8.4% broken · 46.2% pending** (25 / 29 / 10 / 55 out of 119 roadmap items) — down from 25.2% done last pass, despite four new subsystems landing.

**Why "done" went down even though real new code landed:** the `AISettings.top_p`/`top_k` regression (see Broken, below) breaks `LLMManager` construction outright, which cascades into every phase whose "done" status depended on a live proof through the chat/graph/LLM path — LangChain (Chat Models + all 4 providers), LangGraph (the live agent-turn proof), and Session Management (the live chat-persistence proof) all got knocked from done/partial down to broken this pass, for the same root cause. Meanwhile Deployment went from 0% pending to 0%-done-but-100%-partial — real Docker/Compose/Alembic files exist now, each with concrete bugs (wrong healthcheck path, an empty dev-compose file, a corrupted shell script, an "initial" migration that doesn't create tables) that keep them from counting as done. Net: more of the roadmap now has *real, broken* code behind it instead of *nothing* — arguably progress, but not the kind the "% done" column rewards, and the regression is a one-line fix away from restoring last pass's proven-working state.

---

## ✅ Done — properly implemented and proven

### Foundation
| Item | Evidence |
|---|---|
| Configuration & environment management | 12 typed `pydantic-settings` modules under `packages/config/` (`app.py`, `api.py`, `db.py`, `redis.py`, `security.py`, `storage.py`, `queue.py`, `features.py`, `ai.py`, `iam.py`, `upload_service.py`, `notification.py`), env-backed via `.env` |
| FastAPI application | `packages/api/app.py` — real app factory + `lifespan` (`packages/api/lifespan.py`), not a placeholder |
| Exception handling (structure) | `packages/api/exception_handlers.py` — maps `RequestValidationError` → 422, `HTTPException` → passthrough status, unhandled `Exception` → 500, all through one `ErrorResponse` envelope (`packages/api/responses.py`) |
| OpenAPI | `/docs`, `/redoc`, `/openapi.json` live with real title/description/version, per-route summaries |
| Health checks | `packages/api/routers/health.py` — genuinely checks Postgres and Redis connectivity, confirmed live returning `{"status":"degraded","database":"unhealthy","redis":"unhealthy"}` when neither is reachable — real logic, unregressed |
| Logging | `packages/shared/logging.py` (structlog) + `packages/api/middleware/request_id.py` — confirmed emitting structured logs with request IDs on real requests |
| Tenant-context middleware | `packages/api/middleware/tenant.py` (63 lines) + `packages/api/security.py`'s `get_tenant_id` dependency — reads `X-Tenant-ID`/`X-Organization-ID` headers into `request.state`, enforced on every `/api/v1/*` route via `Depends(get_tenant_id)` in `packages/api/routers/__init__.py`. **Caveat:** presence only, no verification — see Pending → IAM |

### Database
| Item | Evidence |
|---|---|
| Conversation & Message models | `packages/domain/models/conversation.py` (190 lines), `message.py` (237 lines), citations modeled |
| Knowledge Base / Document / Chunk / Embeddings models | 4 SQLAlchemy models present under `packages/domain/models/` |
| Prompt Templates / Model Configurations | `prompt.py`, `prompt_version.py`, `model_profile.py` |
| Repository layer (11 classes) | `packages/infrastructure/repositories/` — import cleanly, circular import between `knowledge_base.py`/`agent_knowledge_base.py` resolved with `TYPE_CHECKING` guards |
| Repository layer, at runtime (models/schema) | `packages/infrastructure/database/session.py`'s `create_session()` returns a real `AsyncSession` (not the raw `async_sessionmaker`) — session *construction* is still sound. **But durability regressed this pass**: see Broken → "commit calls removed again." |

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
| Redis connectivity | `packages/infrastructure/redis/` client wrapper + health check — confirmed live and healthy via the real `/health` endpoint |
| Configuration management | Same as Foundation row above — solid |

---

## 🔴 Broken — real code exists but currently fails

| Item | File(s) | What's wrong |
|---|---|---|
| **`AISettings` missing `top_p`/`top_k` — breaks every chat request** | `packages/infrastructure/ai/config.py:38-39`, `packages/config/ai.py`, `packages/infrastructure/ai/manager.py:24` | New this pass, and the single highest-priority bug in the repo. `get_default_llm_config()` reads `settings.ai.top_p` and `settings.ai.top_k` — but `AISettings` defines no such fields. `LLMManager.__init__` calls this at construction time, so **any** resolution of the `ai`/`graph`/`memory` container branches now raises `AttributeError: 'AISettings' object has no attribute 'top_p'`. Confirmed live: `POST /api/v1/chat` crashes with this exact error during dependency-injection, before the route handler runs. This is the same class of container-construction crash fixed twice before (the `LLMRegistry()` mismatch, then the `top_p`-less `AISettings`) — a one-line fix (add the two fields to `AISettings`), but as committed today it undoes essentially all of the previous pass's live-verified proof that chat/graph/tools work end to end. |
| Repository writes no longer commit — regression | `packages/infrastructure/repositories/base.py` | Commit `6fe7723` ("pagination/filters/ordering") silently **removed** the `await self.session.commit()` calls that `d48ce50` had explicitly added to `create()`/`update()`/`delete()`/`delete_by_id()` one pass ago (confirmed via `git log -p` showing the added-then-removed lines). All four write methods now only `flush()`. Combined with the still-unfixed gap #5 (no per-request session close), this means chat writes on the live path are flushed into the transaction but never durably committed unless something else calls `commit()` — a real regression, not a new discovery. |
| Orphaned `packages/application/` service layer — unwired, and broken on its own terms | `packages/application/services/{chat_service,conversation_service,message_service,runtime_service,history_services}.py` | A large new parallel implementation of chat/conversation logic (DTOs, mappers, validators, services) that **nothing outside `packages/application/` imports** — not the DI container, not any router. It's also broken internally: `ChatService._execute_runtime()` is hardcoded to return `"Hello! AI Runtime is not connected yet."` and never calls the runtime at all; `ChatService.touch()`/`ConversationService.close()` call `datetime.utcnow()`/`datetime.now(datetime.UTC)` with only `import datetime` (the module, not the class) imported, a guaranteed `AttributeError` if ever executed; and `history_services.py` imports `from packages.domain.repositories.message import MessageRepository`, but `packages/domain/repositories/` **does not exist** (the real `MessageRepository` lives at `packages/infrastructure/repositories/message.py`) — confirmed `ModuleNotFoundError` in the import sweep. Same pattern as the old dead `infrastructure/ai/factory.py`: real-looking code that is never actually reached. |
| Exception handler — traceback leak closed, but replaced by a worse bug (uncommitted, in progress) | `packages/api/exception_handlers.py` | An in-progress fix now gates the traceback behind `if settings.app.debug:` — a real improvement in intent. But `from packages.config import settings` imports the **`packages/config/settings.py` submodule**, not the actual settings instance (`packages.config.loader.settings`) — so `settings.app.debug` raises `AttributeError: module 'packages.config.settings' has no attribute 'app'` unconditionally, regardless of the real `DEBUG` value. Worse: it never even reaches that line — `logger.exception(...)` itself crashes first with a live-confirmed `UnicodeEncodeError` (Rich/structlog writing a character Windows' cp1252 console can't encode — the same class of bug as the earlier `GraphVisualizer` ✅-emoji crash). Confirmed live with `raise_server_exceptions=True`: the exception that actually propagates out of a request is this `UnicodeEncodeError`, not whatever originally triggered the 500. **Net effect: every 500 response now returns a completely empty body** — no JSON envelope, no error code, nothing — which is arguably worse for API consumers than the traceback leak it replaced, even though it closes the info-disclosure risk. Also stray leftover imports in the diff: `from docx import settings` (immediately shadowed, harmless but bizarre) and `from fastapi import ... logger` (also shadowed two lines later). |
| Weather tool functionally broken | `packages/tools/builtin/weather.py:55-70`, `.env:118` | `OPENWEATHER_BASE_URL=https://api.openweathermap.org/data/2.5` is missing the `/weather` path segment (note: fixed in `.env.example`, but the real `.env` was deliberately left unchanged per an earlier sync-only request), so every real call 404s. The `except httpx.HTTPStatusError` branch silently reports this as `"City '<x>' not found."` instead of surfacing the real config error. |
| Dead orphaned provider factory (old) | `packages/infrastructure/ai/factory.py` | Still imports `AnthropicProvider`/`GoogleProvider`/`GroqProvider`/`OpenAIProvider` from `.registry`, which no longer defines those names → `ImportError` on import. **Note:** a *different*, real replacement now exists at `packages/infrastructure/ai/providers/factory.py` (see LangChain section) — this old file at `infrastructure/ai/factory.py` is pure leftover cruft and should just be deleted. `registry.py`'s `LLMRegistry` is also now dead weight: `container/ai.py` still instantiates it as an unused `registry` Singleton that nothing calls, since `manager.py` switched to the new `providers/factory.py` path. |
| Stale `AgentState` import | `packages/conversation/store.py`, `packages/conversation/memory_store.py`, `packages/application/application.py` | All three still `from packages.graph.state import AgentState`, which was renamed to `GraphState`. Not on the live chat path, but will raise `ImportError` if anything ever imports them. |
| Upload SDK wrong import | `sdk/upload/client.py:5` | `from packages.config.upload import UploadSettings` — the real file is `packages/config/upload_service.py`, the real class is `UploadServiceSettings`. Breaks 8 modules. |
| Notification SDK missing dependency | `sdk/notification/` (5 modules) | Requires the `email-validator` extra, which isn't installed in the venv. |
| `sdk/common/models.py` | `sdk/common/models.py` | `NameError: name 'Pagination' is not defined` — bare names declared with no class definitions behind them. |

**Previously broken, now fixed:** the `GraphVisualizer.save_png()` regression (network call to mermaid.ink + Windows console crash) is properly committed and gone — `packages/graph/manager.py:16` is committed with the call commented out (`8e64b11`).

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

### 5. Async session handling — partially fixed this pass (uncommitted, in progress)
- **Fixed:** `packages/api/dependencies.py`'s `get_db_session` is now an async generator — `try: yield session / finally: await session.close()` — so the per-request session actually closes now. Confirmed by re-running the import sweep and a live request; no regressions found from this specific change.
- **Fixed:** `packages/infrastructure/repositories/unit_of_work.py`'s `UnitOfWork.__aexit__` now correctly does `rollback()` on exception / `commit()` otherwise, always `close()`s in a `finally` block. Still not used on the live chat path (see below), but the pattern itself is now sound where it previously had a bug of its own.
- **Still open:** `packages/infrastructure/repositories/base.py`'s `create()`/`update()`/`delete()` still call only `flush()`, no `commit()` (see Broken → "Repository writes no longer commit") and still no `try/except` around it — a write that raises leaves the session in a failed-transaction state, which now at least gets `close()`d afterward (via the `get_db_session` fix above) rather than leaking, but still isn't rolled back cleanly mid-request.
- **Still open:** the live chat path still goes through `get_db_session`/repositories directly, not `UnitOfWork` — the now-correct `UnitOfWork` pattern exists in the codebase but isn't the thing actually protecting the chat write path.

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

1. **Fix `AISettings` missing `top_p`/`top_k`** (`packages/config/ai.py`) — still the single highest-priority item in the repo. Two-line fix (add `top_p: float = Field(default=0.95, alias="TOP_P")` and `top_k: int = Field(default=40, alias="TOP_K")`, matching values already sitting unused in `.env`), and it currently blocks *every* chat request.
2. **Fix the exception handler's wrong import** (`packages/api/exception_handlers.py`) — change `from packages.config import settings` to `from packages.config.loader import settings`, matching how every other module in the codebase imports it. As written, `settings.app.debug` always raises `AttributeError`, and a separate `UnicodeEncodeError` in the `logger.exception(...)` call fires even before that — together they mean every 500 currently returns a completely empty body. This is close to right in intent; it just needs the import fixed and the logging call made encoding-safe (or wrapped in its own `try/except` so a logging failure can never mask the real error).
3. **Restore the commit() calls removed from `packages/infrastructure/repositories/base.py`** — `6fe7723` silently reverted a fix from two passes ago; writes on the live chat path are flushed but never durably committed.
4. **Finish and commit the `get_db_session`/`UnitOfWork` session fixes** — both are genuine, correct fixes found uncommitted this pass. Worth committing as-is; consider also wrapping `base.py`'s write methods in `try/except` with rollback, now that the session actually gets closed afterward.
5. **Decide the fate of `packages/application/`** — either wire it into the DI container and routers for real, or delete it. ~1,000 lines of unreachable code with at least three independent bugs of its own (hardcoded fake response, wrong import path, `datetime` module/class confusion).
6. **Delete `infrastructure/ai/factory.py` and the unused `LLMRegistry`** — both superseded by the new `infrastructure/ai/providers/` architecture; neither is referenced by anything real anymore.
7. **Fix the Docker healthcheck path** (`/health` → `/api/v1/health`) and either populate `docker-compose.dev.yml` or remove the `make dev` target that expects it.
8. **Fix the Makefile's `docker/compose/` paths** — that directory doesn't exist; the real compose files are at the repo root.
9. **Fix `docker/scripts/wait-for-db.py`'s corrupted `echo`/`exec` lines** before it's ever actually invoked.
10. **Wire real JWT validation** behind the existing tenant-context middleware, and add CORS middleware (gap #2).
11. **Regenerate the Alembic "initial schema" migration properly** — the current one only does an `alter_column` and would fail against a genuinely empty database; it needs real `create_table` calls for all 15+ domain models, or should stop being called "Initial schema."
12. **Wire up at least the Conversations router** — there's still no HTTP-reachable way to create a conversation.
13. **Write an actual pytest suite** — zero automated regression protection anywhere in the repo; this pass's regressions (items 1–3 above) are exactly the kind a CI test suite exists to catch.
14. **Fix the vectorstore backend silent-`None` fallthrough** for faiss/qdrant (gap #8).
15. **Write a real README** — setup steps, required env vars, how to run the server locally.
16. **Close the weather tool's `httpx.AsyncClient`** on shutdown (or switch to the per-call pattern `news.py`/`search.py` already use), and fix `OPENWEATHER_BASE_URL`/`UPLOAD_SERVICE_URL` in the real `.env` now that `.env.example` documents the correct values.
