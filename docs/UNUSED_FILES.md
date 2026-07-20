# Unused / Unnecessary Files

A cleanup inventory for `langchain-knoledgebase-rag`, updated 2026-07-20 (HEAD `e5d8709`) by tracing actual imports from every real entry point (`main.py`, `cli.py`, `packages/api/app.py`, `packages/worker/main.py`) and the DI container graph — not just grepping for file names. Companion to [`docs/BUILD_STATUS.md`](./BUILD_STATUS.md), which tracks correctness; this tracks what shouldn't be in the repo at all, or isn't reachable by anything that runs.

**Update since first written:** five recommendations from this doc have now been acted on — `packages/infrastructure/repositories/__init__.zip` (deleted early on); `packages/graph.zip` (deleted in commit `ff11edd`, twelfth audit pass); and, in the same session, by explicit request, the `GraphPlanner`/`PlannerResult` triplication was resolved by deleting the two losing duplicates outright: `packages/graph/planner.py`, `packages/graph/nodes/planner.py`, and `packages/graph/nodessss.py` (which only existed to import the now-gone `nodes/planner.py`). Everything else below is still present. An earlier commit's message claimed "remove unused files" when the diff didn't touch anything on this list — worth noting these deletions are genuine exceptions to that pattern, not a repeat of it.

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
| `packages.zip` (repo root, ~232 KB) — **still committed** | A full zip snapshot of the entire `packages/` source tree, committed in `e5d8709`. Still present, unchanged, twelve passes running. |
| `graph.png` (repo root) | Still present, unchanged. Generated output from `GraphVisualizer.save_png()` — a build artifact, not source. `.gitignore` still doesn't exclude it. It is at least being correctly regenerated now (`lifespan.py`'s missing `await` fix means it updates on every startup instead of silently failing to render). |

**Fix:** `git rm packages.zip graph.png`, then add `*.zip` and a root-level `graph.png` rule to `.gitignore` so they can't be re-committed.

## Duplicate dependency manifest

| File | Why it's redundant |
|---|---|
| `requirements.txt` (99 lines, unpinned) | Duplicates `pyproject.toml`'s `dependencies` list (67 lines, with version floors) and the `uv.lock` file that pins exact resolved versions. Two manifests for the same dependency set can silently drift out of sync — `pyproject.toml` + `uv.lock` is already the real source of truth (confirmed: `uv sync` in `docker/Dockerfile` uses `pyproject.toml`/`uv.lock`, not `requirements.txt`). |

**Fix:** delete `requirements.txt`, or regenerate it from `uv export` if something outside this repo still needs a flat pip-installable file.

---

## Confirmed unused Python modules

Verified via `grep` for every plausible import path (`from packages.X import`, `packages.X.Y`, etc.) across all of `packages/`, `cli.py`, and `main.py` — none of these are referenced anywhere outside themselves.

### `packages/application/` — ~1,000 lines, entirely orphaned
The whole package, with one small nuance explained below.

| Path | Status |
|---|---|
| `packages/application/dto/*.py` (7 files) | Confirmed unused — nothing outside `packages/application/` imports `application.dto`. |
| `packages/application/mappers/*.py` (2 files) | Confirmed unused. |
| `packages/application/validators/*.py` (2 files) | Confirmed unused. |
| `packages/application/exceptions.py` | Confirmed unused. |
| `packages/application/application.py` | Confirmed unused — its only meaningful import (`packages.conversation.store`) is itself dead code (see below). |
| `packages/application/services/conversation_service.py` | Confirmed unused. |
| `packages/application/services/message_service.py` | Confirmed unused. |
| `packages/application/services/runtime_service.py` | Confirmed unused. |
| `packages/application/services/history_services.py` | Confirmed unused (also currently broken — imports `packages.domain.repositories.message`, which doesn't exist; real path is `packages.infrastructure.repositories.message`). |
| `packages/application/services/{agent,document,embedding,knowledge_base,model_profile,prompt,rag,tool}_service.py` (8 files) | Confirmed unused — each is a 1-line comment stub (`# agent_service.py` etc.), never implemented. |
| `packages/application/services/chat_service.py` | **Nuance, not a false positive:** `packages/rag/manager.py` does `from packages.application.services.chat_service import ChatService` and type-hints a constructor parameter with it — but the actual object injected at that parameter (`chat_service=services.chat` in `packages/infrastructure/container/rag.py:84`) resolves to a *different* class, `packages.chat.chat_service.ChatService` (see `packages/infrastructure/container/services.py:7,26-29`). Python doesn't enforce type hints at runtime, so this "works," but the import is a red herring — this specific file is never actually instantiated or called anywhere. Even if it were, its `_execute_runtime()` is hardcoded to return `"Hello! AI Runtime is not connected yet."` and never calls anything real. |

**Recommendation:** delete the whole package. It's a second, incomplete rewrite of functionality `packages/conversation/` and `packages/chat/` already provide, and every audit pass across this project's history has found it unwired.

### Other confirmed-dead files

| Path | Status |
|---|---|
| `packages/conversation/store.py` | Confirmed unused outside `packages/application/application.py` (itself dead — see above). Also currently broken: imports `AgentState` from `packages.graph.state`, which was renamed to `GraphState` months ago. |
| `packages/conversation/memory_store.py` | Same — unused, same stale `AgentState` import bug. |
| `packages/infrastructure/ai/factory.py` | Confirmed zero references anywhere. Also currently broken — imports `AnthropicProvider`/`GoogleProvider`/`GroqProvider`/`OpenAIProvider` from `.registry`, which no longer defines those names (superseded by `packages/infrastructure/ai/providers/factory.py`, a *different*, real, live file). |
| `packages/sdk/upload/*.py` (8 files: `client.py`, `bulk.py`, `exceptions.py`, `files.py`, `uploads.py`, etc.) | **Relocated, not fixed** — this used to be a top-level `sdk/upload/`; it's now `packages/sdk/upload/`, same 8 files, same bugs. Still confirmed unused outside `packages/sdk/` itself. `client.py` still imports `UploadSettings` from `packages.config.upload`, which doesn't exist (real path: `packages/config/upload_service.py`, real class: `UploadServiceSettings`). |
| `packages/sdk/notification/*.py` (5 files) | Relocated, not fixed — still unused, still requires the uninstalled `email-validator` package. |
| `packages/sdk/common/models.py` | Relocated, not fixed — still unused, still `NameError: name 'Pagination' is not defined` on import. |
| ~~`packages/graph/nodessss.py`~~ | **Deleted.** The old `packages/graph/nodes.py`, renamed out of the way rather than removed at the time; only existed to import `packages/graph/nodes/planner.py`, which is also now gone. |
| ~~`packages/graph/planner.py`~~ | **Deleted.** The old, standalone `GraphPlanner`/`PlannerResult(next_node: str)` implementation, superseded by the consolidated planner below. |
| ~~`packages/graph/nodes/planner.py`~~ | **Deleted.** This was briefly the live, DI-wired planner (as of the twelfth pass) — superseded the same session when the team chose to consolidate onto `packages/planner/planner.py`'s richer plan-based model instead (see below). |

---

## Wired but never consumed

These are real classes that the DI container constructs — so they "work" in the sense of importing and instantiating cleanly — but nothing anywhere actually calls a method on them or uses the provider they're assigned to. They show up as reachable in an import sweep, which is why they're easy to miss; the container graph is what actually reveals them as dead.

| Path | Evidence |
|---|---|
| `packages/infrastructure/ai/registry.py` (`LLMRegistry`) | `packages/infrastructure/container/ai.py:16-18` constructs `registry = providers.Singleton(LLMRegistry)` — but `manager = providers.Singleton(LLMManager)` (the only other provider in this container) takes no arguments and never references `registry`. Superseded by `packages/infrastructure/ai/providers/factory.py`, which `LLMManager` actually uses now. |
| `packages/rag/pipeline.py` (`RAGPipeline`) | `packages/infrastructure/container/rag.py:68-72` constructs `pipeline = providers.Singleton(RAGPipeline, retriever=retriever, indexer=indexer)` — but no other provider in the container references `pipeline`. The one that actually gets used, `manager = providers.Singleton(RAGManager, retrieval_pipeline=retriever, ...)` (line 78-84), depends on `retriever` directly, not `pipeline`. |
| `packages/rag/retriever.py` (`RetrievalPipeline` — note: a *different* class from the same-named one actually in use, see below) | Only imported by `packages/rag/pipeline.py` (the dead leaf above) — so this file is only reachable through an already-unconsumed provider. |
| `packages/knowledge/manager.py` (`KnowledgeManager`) and the ~70-file `packages/knowledge/` subsystem behind it | `packages/infrastructure/container/rag.py:56-61` constructs `knowledge_manager = providers.Singleton(KnowledgeManager, ingestion_pipeline=providers.Object(None), embedding_manager=providers.Object(None), retriever_manager=providers.Object(None))` — real dependencies replaced with `None` placeholders, and no other provider consumes `knowledge_manager`. Calling any real method on it (`.ingest()`, `.search()`, etc.) would immediately raise `AttributeError: 'NoneType' object has no attribute ...`. See `docs/BUILD_STATUS.md` for the detailed internal-bug list (this package also has real, separate correctness bugs beyond just being unwired). |

**A naming trap worth flagging explicitly:** there are **two different classes both named `RetrievalPipeline`** — `packages/rag/retriever.py`'s (dead, per above) and `packages/rag/pipelines/retrieval.py`'s (the one actually constructed as the `retriever` provider and used by the live `RAGManager`). Same for `ChatService` — `packages/chat/chat_service.py` (live, used by `RAGManager` via `services.chat`) vs. `packages/application/services/chat_service.py` (dead, see above) are two unrelated classes with the same name. **The `GraphPlanner`/`PlannerResult` case is now resolved, unlike the two above:** what had grown to three separate implementations is down to one — `packages/planner/planner.py`, chosen deliberately for its richer plan-based (`ExecutionPlan`/`ExecutionStep`/`Capability`) model, which better fits where the roadmap's Memory/HITL/Summarization phases are headed than a single-hop `next_node` enum would. The two losing duplicates are deleted, not just orphaned. Worth treating this as the template for resolving the still-open `RetrievalPipeline`/`ChatService` pairs above: pick the one with the better long-term shape, delete the other outright.

**Resolved this pass:** `packages/graph/nodes/tool.py`'s `GraphToolNode` is no longer in this category — `packages/infrastructure/container/graph.py` now constructs it (`tool = providers.Singleton(GraphToolNode, tool_manager=tools.manager)`) and wires it into `GraphNodes`. Its own internal bug (calling `tool_manager.get_tools()`, a nonexistent method) is fixed too, now calling the real `tool_manager.list()`.

---

## Fixed in an earlier pass — the copy-pasted `__init__.py` template

Previously flagged: five `__init__.py` files, evidently scaffolded by copying one file without updating its contents, all identically containing `from .manager import MemoryManager` despite none of their directories defining that class. All five (`packages/rag/builders/`, `packages/rag/pipelines/`, `packages/middleware/`, `packages/planner/`, `packages/memory/implementations/`) are now fixed — real, empty `# init` files, confirmed via import sweep. Two of these directories have since grown real content of their own: `packages/memory/implementations/` now holds the genuine `PostgresMemoryStore`/`LLMMemoryExtractor`/`LLMMemorySummarizer`/`PgVectorMemoryRetriever` classes actually wired into `MemoryManager`, and `packages/planner/` is now the sole, live `GraphPlanner` implementation (see above) — the empty scaffolding both grew into is real, load-bearing code now.

---

## Not included in this list

- `packages/infrastructure/database/migrations.py` fails to import standalone (`AttributeError: module 'alembic.context' has no attribute 'config'`) — this is **expected**, not dead code. It's an Alembic `env.py`-style module that only works inside an active `alembic` CLI invocation; it's genuinely used by `alembic/env.py`.
- `packages/knowledge/`'s loaders, embeddings, splitters, and retrievers that are internally broken (wrong class-name imports, method-signature mismatches) but *would* be reachable if `knowledge_manager`'s wiring were completed — these are tracked as correctness bugs in `docs/BUILD_STATUS.md`, not listed here as "unused," since the intent is clearly for them to be used once finished.
- Anything under `.venv/`, `__pycache__/`, `logs/`, `storage/`, `uploads/`, `temp/` — already correctly gitignored, not tracked.

---

## Suggested cleanup order

1. `git rm packages.zip graph.png`, then add `*.zip` and a root-level `graph.png` rule to `.gitignore`. (`packages/graph.zip` and the `GraphPlanner` duplicates are already gone as of this pass.)
2. Delete `requirements.txt` (or regenerate it from `uv export` if some external process depends on it).
3. Delete `packages/application/` in full, plus `packages/conversation/store.py` and `memory_store.py`.
4. Delete `packages/sdk/upload/`, `packages/sdk/notification/`, `packages/sdk/common/models.py` — or fix their import bugs first if the SDK is meant to be used soon; as-is they're both unused *and* broken.
5. Delete `packages/infrastructure/ai/factory.py` and the `registry` provider in `packages/infrastructure/container/ai.py` (plus its now-unused import of `LLMRegistry`).
6. Decide `packages/rag/pipeline.py`/`packages/rag/retriever.py`'s fate — delete if `packages/rag/pipelines/retrieval.py` is the intended long-term path. Same treatment now applies to `ChatService`'s duplication — pick one, delete the other, following the pattern that just resolved `GraphPlanner`.
7. `packages/knowledge/` remains the one item here worth finishing rather than deleting — real, substantial work with a coherent architecture; see `docs/BUILD_STATUS.md`'s priority list for what's left.
