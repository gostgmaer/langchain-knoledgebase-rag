# Unused / Unnecessary Files

A cleanup inventory for `langchain-knoledgebase-rag`, updated 2026-07-20 (HEAD `e5d8709`) by tracing actual imports from every real entry point (`main.py`, `cli.py`, `packages/api/app.py`, `packages/worker/main.py`) and the DI container graph — not just grepping for file names. Companion to [`docs/BUILD_STATUS.md`](./BUILD_STATUS.md), which tracks correctness; this tracks what shouldn't be in the repo at all, or isn't reachable by anything that runs.

**Update since first written:** five recommendations from this doc have now been acted on — `packages/infrastructure/repositories/__init__.zip` (deleted early on); `packages/graph.zip` (deleted in commit `ff11edd`, twelfth audit pass); and, in the same session, by explicit request, the `GraphPlanner`/`PlannerResult` triplication was resolved by deleting the two losing duplicates outright: `packages/graph/planner.py`, `packages/graph/nodes/planner.py`, and `packages/graph/nodessss.py` (which only existed to import the now-gone `nodes/planner.py`). An earlier commit's message claimed "remove unused files" when the diff didn't touch anything on this list — worth noting these deletions are genuine exceptions to that pattern, not a repeat of it.

**Sixth deletion, thirteenth pass, by explicit request ("remove unnecessary RAG file/folder"):** `packages/rag/` — the entire legacy pre-`packages/knowledge/` RAG implementation (19 files: `manager.py`, `pipeline.py`, `retriever.py`, `indexer.py`, `loader.py`, `splitter.py`, `embeddings.py`, `vectorstore.py`, `document.py`, `models.py`, `schemas.py`, `types.py`, `exceptions.py`, plus `builders/{citation,context,prompt}.py` and `pipelines/retrieval.py`) — deleted outright. Traced its only remaining outside reference: `packages/agent/context.py` importing `Citation`/`Context` from `packages.rag.schemas`. `packages/agent/` (`context.py`, `prompt.py`, `response.py`, `runtime.py`) turned out to be dead too — `packages/infrastructure/container/application.py` wired `prompt_builder`/`agent_runtime` providers from it, but confirmed zero downstream consumers anywhere in `packages/api/` or `packages/application/`. Deleted both packages together, removed the now-dead `prompt_builder`/`agent_runtime` provider wiring and imports from `application.py`. Verified: full DI container construction still succeeds, full import sweep shows the same pre-existing failure set (403/426 OK, was 428/451 OK — the 25-file drop matches the two deleted packages exactly, zero new failures), and a live `POST /api/v1/chat` request still returns `200` with a correct response.

Confidence levels, in order of how sure this doc is:
- **Confirmed unused** — zero references anywhere outside the file/package itself. Safe to delete.
- **Wired but never consumed** — the DI container constructs it (so it "imports fine" and even instantiates), but nothing downstream ever calls it or uses the provider. Deleting it requires removing its container wiring too.
- **Junk / repo hygiene** — not a code-correctness issue, just doesn't belong in version control.

---

## Junk files — repo hygiene, delete immediately

**Status update: two of three are now gone.**

| File | Why it shouldn't be here |
|---|---|
| ~~`packages/infrastructure/repositories/__init__.zip`~~ | **Deleted**, early pass. |
| ~~`packages/graph.zip`~~ | **Deleted** in commit `ff11edd` (twelfth audit pass) — confirmed via `git show --stat HEAD`. |
| ~~`packages.zip`~~ | **Already gone** — re-verified this pass (`ls packages.zip` → not found, `git ls-files` → not tracked). This row had gone stale; whatever pass actually removed it never updated this doc. |
| ~~`graph.png`~~ | **Untracked this pass** (`git rm --cached`) — the file on disk is correctly regenerated on every API startup (as this row already noted), the problem was only that git was still tracking a point-in-time snapshot of a build artifact. `.gitignore` now excludes `/graph.png` and `*.zip` so neither can be re-committed. |

## Duplicate dependency manifest

| File | Why it's redundant |
|---|---|
| ~~`requirements.txt`~~ | **Already gone** — re-verified this pass (`ls requirements.txt` → not found, `git ls-files` → not tracked). Same as `packages.zip` above: already deleted, this doc just never caught up. `pyproject.toml` + `uv.lock` remain the real source of truth. |

---

## Confirmed unused Python modules

Verified via `grep` for every plausible import path (`from packages.X import`, `packages.X.Y`, etc.) across all of `packages/`, `cli.py`, and `main.py` — none of these are referenced anywhere outside themselves.

### `packages/application/` — no longer entirely dead, correction from every prior pass

**Reversal this session:** at the user's explicit request, `ChatService`/`ConversationService`/`MessageService` were fixed (9 real bugs, see `docs/BUILD_STATUS.md`'s milestone section) and wired in as the actual top-level `POST /api/v1/chat` flow, replacing `packages/conversation/manager.py`'s `ConversationManager`. Roughly a third of this package is now live, load-bearing code — not dead weight. The rest is still genuinely unused.

| Path | Status |
|---|---|
| `packages/application/services/chat_service.py` | **Now live** — the real top-level chat entry point, wired via `packages/infrastructure/container/chat_service.py`. Its `_execute_runtime()` was a hardcoded stub (`"Hello! AI Runtime is not connected yet."`); now genuinely invokes `GraphManager`. |
| `packages/application/services/conversation_service.py` | **Now live** — used by `ChatService`. Two real bugs fixed to make it work: a missing `get_by_session_id()` on `ConversationRepository`, and a missing `touch()` method this class never had (despite `ChatService` calling it). |
| `packages/application/services/message_service.py` | **Now live** — used by `ChatService` to persist user/assistant messages. |
| `packages/application/dto/chat.py` (`ChatRequest`, `ChatResponse`) | **Now live** — the request/response shape for the new top-level flow. Note: this is a *third*, distinct `ChatRequest` class in this codebase, alongside `packages.chat.request.ChatRequest` and `packages.conversation.models.ChatRequest` (the now-unused one `ConversationManager` took). |
| `packages/application/dto/conversation.py` (`CreateConversationRequest`, `ConversationResponse`) | **Now live** — used by `ConversationService`. |
| `packages/application/exceptions.py` (`ResourceNotFoundError`, etc.) | **Now live** — real, was previously just never imported by anything. |
| ~~`packages/application/dto/agent.py`, `dto/message.py`~~ | **Deleted this pass.** Re-verified zero references first (`grep -rl` across `packages/`/`cli.py`/`main.py`) — `dto/message.py`'s `CreateMessageRequest`/`MessageResponse` were never actually used by `MessageService` (it takes plain params, not the DTO), confirming the earlier note. `dto/common.py`, `dto/conversation.py`, `dto/knowledge_base.py`, `dto/document.py` are newer, real, live-used additions not reflected in this doc's last update — left alone. |
| ~~`packages/application/mappers/*.py`~~ | **Deleted this pass**, whole directory including `__init__.py` — re-verified zero references to the file, and to `packages.application.mappers` as a package, before removing. |
| ~~`packages/application/validators/*.py`~~ | **Deleted this pass**, whole directory including `__init__.py` — same verification as mappers above. |
| ~~`packages/application/application.py`~~, ~~`runtime_service.py`~~, ~~`history_services.py`~~ | **Already gone** — not present on disk as of this pass (`find packages/application -name "*.py"` doesn't list them). Already deleted in some earlier, undocumented pass; this doc just never caught up. |
| ~~`packages/application/services/{agent,document,embedding,knowledge_base,model_profile,prompt,rag,tool}_service.py`~~ (8 files) | **Deleted this pass** — re-verified each was still a genuine 1-line comment stub with zero references before removing. Real documents/knowledge_bases functionality lives in `packages/api/routers/` + `packages/infrastructure/repositories/` directly, never routed through these stubs. |

**Practical impact of this reversal:** `packages/conversation/manager.py`'s `ConversationManager` — previously the live top-level flow, extensively tested across the last several audit passes — became unused once `ChatService` took over. **Now deleted, dedicated pass:** see "New this pass" below for the full account.

**Recommendation, updated:** do not delete the whole package — `chat_service.py`/`conversation_service.py`/`message_service.py`/`audit_service.py`/`feature_flag_service.py`/`ingestion_audit.py`/`reindex.py`/`retention_service.py`/`retrieval_log_service.py`/`retrieval_settings_service.py` and their matching DTOs are all live, several of them (`retention_service`, `reindex`, `audit_service`, `retrieval_settings_service`) added after this doc's last update and genuinely wired into real routes. The confirmed-dead parts (mappers, validators, the 8 stub services, the two dead DTOs) are now gone.

### Other confirmed-dead files

| Path | Status |
|---|---|
| ~~`packages/conversation/store.py`~~ | **Deleted** (a later pass) — confirmed unused outside `packages/application/application.py` (itself dead — see above), and broken (a stale `AgentState` import from before it was renamed to `GraphState`). |
| ~~`packages/conversation/memory_store.py`~~ | **Deleted** (a later pass) — same reasoning as `store.py` above. |
| ~~`packages/infrastructure/ai/factory.py`~~ | **Deleted** (a later pass) — zero references anywhere, and broken (imported names `.registry` no longer defines, superseded by `packages/infrastructure/ai/providers/factory.py`, a *different*, real, live file). |
| ~~`packages/sdk/upload/*.py`~~ | **Fixed and wired in for real, no longer dead code.** `client.py`'s broken import corrected (`packages.config.upload_service.UploadServiceSettings`, not the nonexistent `packages.config.upload.UploadSettings`); new `packages/infrastructure/container/upload.py` (`UploadContainer`) constructs a real `UploadClient` the same way `packages/infrastructure/container/iam.py` wires the IAM SDK, wired into `ApplicationContainer` as `container.upload`. `packages/api/routers/documents.py`'s upload route now calls it as the durable file store, ahead of a short-lived local scratch copy for the ingestion pipeline. See `docs/ARCHITECTURE_TUTORIAL.md` §5.1/§13 and `docs/CHANGELOG.md`. |
| ~~`packages/sdk/notification/*.py`~~ (5 files) | **Deleted** — re-confirmed zero references anywhere (`grep -rl "sdk.notification"` across `packages/`/`tests/`) before removing, docs/BUGS.md item 24. |
| `packages/sdk/common/models.py` | **File no longer exists** — already deleted in an earlier pass, this row just never got removed. |
| ~~`packages/graph/nodessss.py`~~ | **Deleted.** The old `packages/graph/nodes.py`, renamed out of the way rather than removed at the time; only existed to import `packages/graph/nodes/planner.py`, which is also now gone. |
| ~~`packages/graph/planner.py`~~ | **Deleted.** The old, standalone `GraphPlanner`/`PlannerResult(next_node: str)` implementation, superseded by the consolidated planner below. |
| ~~`packages/graph/nodes/planner.py`~~ | **Deleted.** This was briefly the live, DI-wired planner (as of the twelfth pass) — superseded the same session when the team chose to consolidate onto `packages/planner/planner.py`'s richer plan-based model instead (see below). |

---

## Wired but never consumed

These are real classes that the DI container constructs — so they "work" in the sense of importing and instantiating cleanly — but nothing anywhere actually calls a method on them or uses the provider they're assigned to. They show up as reachable in an import sweep, which is why they're easy to miss; the container graph is what actually reveals them as dead.

| Path | Evidence |
|---|---|
| `packages/infrastructure/ai/registry.py` (`LLMRegistry`) | `packages/infrastructure/container/ai.py:16-18` constructs `registry = providers.Singleton(LLMRegistry)` — but `manager = providers.Singleton(LLMManager)` (the only other provider in this container) takes no arguments and never references `registry`. Superseded by `packages/infrastructure/ai/providers/factory.py`, which `LLMManager` actually uses now. |
| ~~`packages/rag/pipeline.py` (`RAGPipeline`)~~ | **Deleted, thirteenth pass** — `packages/rag/` in full, see above. `packages/infrastructure/container/rag.py` had long since moved on to `packages/knowledge/`'s `RetrieverFactory`/`KnowledgeManager` and never referenced this. |
| ~~`packages/rag/retriever.py` (`RetrievalPipeline`)~~ | **Deleted, thirteenth pass** — same removal. |
| ~~`packages/conversation/manager.py` (`ConversationManager`)~~, ~~`service.py`~~, ~~`summarizer.py`~~, ~~`models.py`~~ (`ChatRequest`/`ChatResponse`/`ConversationContext`), ~~`packages/api/dependencies.py`'s `get_conversation_manager`~~ | **Deleted, a dedicated pass** (not bundled into the general stub-file cleanup above, per that cleanup's own note that this needed its own pass). Traced the full dependency chain first: `get_conversation_manager` had zero route callers (confirmed via grep across `packages/api/routers/`); `ConversationManager` was its only consumer; `ConversationService`/`ConversationSummarizer`/`models.py`'s `ChatRequest`/`ChatResponse`/`ConversationContext` were each in turn only ever consumed by `ConversationManager` or its container wiring, nothing else, confirmed via `grep -rln` from each file outward. `ConversationContextBuilder`/`MessageFormatter`/`ConversationHistory` are the genuinely shared survivors — `ChatService` depends on `ConversationContextBuilder` directly, which itself depends on the other two internally (`packages/conversation/context.py`'s constructor) — kept, along with a trimmed `ConversationContainer` (`packages/infrastructure/container/conversation.py`) exposing only `context`/`history`/`formatter`, and `packages/conversation/__init__.py` updated to match. Verified: a full repo-wide import sweep (463 modules under `packages/`) is 100% clean, zero failures; `ApplicationContainer()` constructs and resolves `conversation.context`/`conversation.history` without error. Full live verification (a real `POST /api/v1/chat` round trip) deferred — this environment's Docker Desktop was down for this pass; the static checks above are strong evidence but not a substitute for that. |
| ~~`packages/knowledge/manager.py` (`KnowledgeManager`) and the `packages/knowledge/` subsystem behind it~~ | **No longer accurate — reversed across several later passes.** `packages/knowledge/` is now the canonical, live-wired RAG/document-processing stack: `KnowledgeManager` is genuinely constructed with real `ingestion_pipeline`/`embedding_manager`/`retriever_manager` collaborators in `packages/infrastructure/container/rag.py`, used by `POST /api/v1/documents`, `RetrieveNode`, and (as of the thirteenth pass) a real hybrid/BM25/re-ranking retrieval path. See `docs/BUILD_STATUS.md`'s Document Processing and Production Retrieval sections. |

**The `RetrievalPipeline` naming-collision half of this note is now moot** — both classes lived inside the now-deleted `packages/rag/`. **The `ChatService`/`ChatRequest` collision is still real and unresolved**, just at a different pair of layers than originally flagged: `packages/application/services/chat_service.py`'s `ChatService` is the live top-level `POST /api/v1/chat` flow, and it calls `packages/chat/chat_service.py`'s separate, still-live `ChatService.achat()` internally (via `packages/graph/nodes/llm.py`'s `LLMNode`) — two same-named classes, both genuinely live, at different layers. `packages.application.dto.chat.ChatRequest` and `packages.chat.request.ChatRequest` are the corresponding two live `ChatRequest` classes (`packages.conversation.models.ChatRequest`, the third, is unused — see "Wired but never consumed" above). The `GraphPlanner`/`PlannerResult` case remains the resolved template for collapsing this kind of duplication: pick one layer's shape, delete the rest outright.

**Resolved this pass:** `packages/graph/nodes/tool.py`'s `GraphToolNode` is no longer in this category — `packages/infrastructure/container/graph.py` now constructs it (`tool = providers.Singleton(GraphToolNode, tool_manager=tools.manager)`) and wires it into `GraphNodes`. Its own internal bug (calling `tool_manager.get_tools()`, a nonexistent method) is fixed too, now calling the real `tool_manager.list()`.

---

## Fixed in an earlier pass — the copy-pasted `__init__.py` template

Previously flagged: five `__init__.py` files, evidently scaffolded by copying one file without updating its contents, all identically containing `from .manager import MemoryManager` despite none of their directories defining that class. All five (`packages/rag/builders/`, `packages/rag/pipelines/`, `packages/middleware/`, `packages/planner/`, `packages/memory/implementations/`) are now fixed — real, empty `# init` files, confirmed via import sweep. Two of these directories have since grown real content of their own: `packages/memory/implementations/` now holds the genuine `PostgresMemoryStore`/`LLMMemoryExtractor`/`LLMMemorySummarizer`/`PgVectorMemoryRetriever` classes actually wired into `MemoryManager`, and `packages/planner/` is now the sole, live `GraphPlanner` implementation (see above) — the empty scaffolding both grew into is real, load-bearing code now.

---

## Not included in this list

- `packages/infrastructure/database/migrations.py` fails to import standalone (`AttributeError: module 'alembic.context' has no attribute 'config'`) — this is **expected**, not dead code. It's an Alembic `env.py`-style module that only works inside an active `alembic` CLI invocation; it's genuinely used by `alembic/env.py`.
- `packages/knowledge/` — no longer applicable here at all. It's the canonical, live-wired RAG/document-processing stack as of several passes ago (see `docs/BUILD_STATUS.md`'s Document Processing and Production Retrieval sections); nothing in it is unused or unreachable.
- Anything under `.venv/`, `__pycache__/`, `logs/`, `storage/`, `uploads/`, `temp/` — already correctly gitignored, not tracked.

---

## Suggested cleanup order

1. ~~`git rm packages.zip graph.png`, add `*.zip`/`graph.png` to `.gitignore`.~~ — **Done.** `packages.zip` was already gone (this doc just hadn't caught up); `graph.png` untracked and `.gitignore` updated this pass.
2. ~~Delete `requirements.txt`.~~ — **Already gone**, same as `packages.zip` — this doc hadn't caught up.
3. ~~Delete only the still-dead parts of `packages/application/`~~ — **Done this pass**: `mappers/`, `validators/`, the 8 stub `*_service.py` files, and the 2 dead DTOs (`dto/agent.py`, `dto/message.py`). `application.py`/`runtime_service.py`/`history_services.py` were already gone. **Not the whole package** — see the updated recommendation above for what's genuinely live now.
4. `packages/sdk/upload/` is done, not a cleanup target — fixed and wired in for real (see above). `packages/sdk/notification/` is deleted (a later pass); `packages/sdk/common/models.py` no longer exists either.
5. ~~Delete `packages/infrastructure/ai/factory.py`...~~ — **Already gone** (re-verified this pass: not on disk). This item contradicted the "Other confirmed-dead files" table above, which already correctly said it was deleted — just never removed from this list.
6. ~~Decide `packages/conversation/manager.py`'s now-fully-dead `ConversationManager`...~~ — **Done, a dedicated pass.** See the "New this pass" row above for the full account.
7. **Still open, deliberately not done**: resolve the `ChatService`/`ChatRequest` duplication (`packages/application/services/chat_service.py` vs. `packages/chat/chat_service.py`) — pick one layer's shape, delete the rest, following the same pattern. Both are genuinely live today (confirmed this pass), so this is a real design decision about which layer's shape wins, not a dead-code deletion — out of scope for a cleanup pass.
7. `packages/knowledge/` is done, not a cleanup target — it's the canonical, live RAG stack; see `docs/BUILD_STATUS.md`.
