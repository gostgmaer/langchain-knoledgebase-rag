# Unused / Unnecessary Files

A cleanup inventory for `langchain-knoledgebase-rag`, updated 2026-07-20 (HEAD `e5d8709`) by tracing actual imports from every real entry point (`main.py`, `cli.py`, `packages/api/app.py`, `packages/worker/main.py`) and the DI container graph — not just grepping for file names. Companion to [`docs/BUILD_STATUS.md`](./BUILD_STATUS.md), which tracks correctness; this tracks what shouldn't be in the repo at all, or isn't reachable by anything that runs.

**Update since first written:** one recommendation from this doc was acted on (`packages/infrastructure/repositories/__init__.zip` was deleted) — but the same accidental-zip pattern recurred at a larger scope in the same commit, and the top-level `sdk/` directory this doc originally covered was relocated (not fixed) to `packages/sdk/`. See below.

Confidence levels, in order of how sure this doc is:
- **Confirmed unused** — zero references anywhere outside the file/package itself. Safe to delete.
- **Wired but never consumed** — the DI container constructs it (so it "imports fine" and even instantiates), but nothing downstream ever calls it or uses the provider. Deleting it requires removing its container wiring too.
- **Junk / repo hygiene** — not a code-correctness issue, just doesn't belong in version control.

---

## Junk files — repo hygiene, delete immediately

**Status update: one deleted, two larger ones took its place — and both are now committed to git history, not just sitting untracked.**

| File | Why it shouldn't be here |
|---|---|
| ~~`packages/infrastructure/repositories/__init__.zip`~~ | **Deleted** in commit `e5d8709` — the one cleanup recommendation from this doc that landed. |
| `packages.zip` (repo root, ~236 KB) — **new, committed** | A full zip snapshot of the entire `packages/` source tree, committed in `e5d8709` alongside the very refactor that broke the app (see `docs/BUILD_STATUS.md`'s two app-breaking bugs this pass). Same accidental-IDE-backup pattern as before, now at whole-project scope. |
| `packages/graph.zip` — **new, committed** | A zip snapshot of `packages/graph/`, sitting as a sibling *file* next to the `packages/graph/` *directory* — includes the very `nodes.py`/`nodes/` files whose collision broke the app this pass. Also committed in `e5d8709`. |
| `graph.png` (repo root) | Still present, unchanged. Generated output from `GraphVisualizer.save_png()` — a build artifact, not source. `.gitignore` still doesn't exclude it. |

**Fix:** `git rm packages.zip packages/graph.zip graph.png`. Since two of these are now committed to history (not just working-tree cruft), this needs an actual commit, not just a `.gitignore` addition — add `*.zip` and a root-level `graph.png` rule to `.gitignore` afterward so they can't be re-committed. Worth raising as a process question too: this is the second time a zip snapshot has been committed by accident, now at a larger scope than the first time — whatever tool or habit is producing these (IDE auto-backup, a packaging script run in the wrong directory) is worth identifying so it stops recurring.

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

---

## Wired but never consumed

These are real classes that the DI container constructs — so they "work" in the sense of importing and instantiating cleanly — but nothing anywhere actually calls a method on them or uses the provider they're assigned to. They show up as reachable in an import sweep, which is why they're easy to miss; the container graph is what actually reveals them as dead.

| Path | Evidence |
|---|---|
| `packages/infrastructure/ai/registry.py` (`LLMRegistry`) | `packages/infrastructure/container/ai.py:16-18` constructs `registry = providers.Singleton(LLMRegistry)` — but `manager = providers.Singleton(LLMManager)` (the only other provider in this container) takes no arguments and never references `registry`. Superseded by `packages/infrastructure/ai/providers/factory.py`, which `LLMManager` actually uses now. |
| `packages/rag/pipeline.py` (`RAGPipeline`) | `packages/infrastructure/container/rag.py:68-72` constructs `pipeline = providers.Singleton(RAGPipeline, retriever=retriever, indexer=indexer)` — but no other provider in the container references `pipeline`. The one that actually gets used, `manager = providers.Singleton(RAGManager, retrieval_pipeline=retriever, ...)` (line 78-84), depends on `retriever` directly, not `pipeline`. |
| `packages/rag/retriever.py` (`RetrievalPipeline` — note: a *different* class from the same-named one actually in use, see below) | Only imported by `packages/rag/pipeline.py` (the dead leaf above) — so this file is only reachable through an already-unconsumed provider. |
| `packages/knowledge/manager.py` (`KnowledgeManager`) and the ~70-file `packages/knowledge/` subsystem behind it | `packages/infrastructure/container/rag.py:56-61` constructs `knowledge_manager = providers.Singleton(KnowledgeManager, ingestion_pipeline=providers.Object(None), embedding_manager=providers.Object(None), retriever_manager=providers.Object(None))` — real dependencies replaced with `None` placeholders, and no other provider consumes `knowledge_manager`. Calling any real method on it (`.ingest()`, `.search()`, etc.) would immediately raise `AttributeError: 'NoneType' object has no attribute ...`. See `docs/BUILD_STATUS.md` for the detailed internal-bug list (this package also has real, separate correctness bugs beyond just being unwired). |

**A naming trap worth flagging explicitly:** there are **two different classes both named `RetrievalPipeline`** — `packages/rag/retriever.py`'s (dead, per above) and `packages/rag/pipelines/retrieval.py`'s (the one actually constructed as the `retriever` provider and used by the live `RAGManager`). Same for `ChatService` — `packages/chat/chat_service.py` (live, used by `RAGManager` via `services.chat`) vs. `packages/application/services/chat_service.py` (dead, see above) are two unrelated classes with the same name. **A third instance appeared this pass:** `packages/graph/planner.py` and `packages/graph/nodes/planner.py` each define a different `PlannerResult` class, and `packages/graph/state.py`/`packages/graph/router.py` reference the two inconsistently (see `docs/BUILD_STATUS.md` for the live-breaking bug this is entangled with). All three collisions make it easy to misjudge what's actually running just by grepping a class name — worth renaming one side of each pair to prevent future confusion, independent of the cleanup itself.

---

## New this pass — a copy-pasted `__init__.py` template, spreading

A distinct pattern from the "orphaned code" above: five new `__init__.py` files, evidently scaffolded by copying one file without updating its contents, all containing the identical:
```python
# init
from .manager import MemoryManager
__all__ = ["MemoryManager"]
```
None of the five directories they live in actually has a `manager.py` defining `MemoryManager` (the real one lives in `packages/memory/manager.py`, one level up from where it's expected). This isn't "unused" in the same sense as the rest of this document — two of these five are on the live request path and are actively breaking the app (tracked as the top Broken items in `docs/BUILD_STATUS.md` this pass); the other three are inert scaffolding that will break the moment anyone tries to use them.

| Path | Live impact |
|---|---|
| `packages/rag/builders/__init__.py` | **Breaks the live app** — imported by `packages/infrastructure/container/rag.py` and `packages/rag/manager.py`. |
| `packages/rag/pipelines/__init__.py` | **Breaks the live app** — same import chain. |
| `packages/middleware/__init__.py` | Not yet imported by anything (confirmed via grep) — inert until something tries to use it. |
| `packages/planner/__init__.py` | Not yet imported by anything — inert until something tries to use it. |
| `packages/memory/implementations/__init__.py` | Not yet imported by anything outside `packages/memory/` itself, but would break immediately if it were — it looks one directory level too deep for `MemoryManager`. |

**Fix:** replace all five with real (or simply empty) `__init__.py` files — none of them should reference `MemoryManager` at all.

---

## Not included in this list

- `packages/infrastructure/database/migrations.py` fails to import standalone (`AttributeError: module 'alembic.context' has no attribute 'config'`) — this is **expected**, not dead code. It's an Alembic `env.py`-style module that only works inside an active `alembic` CLI invocation; it's genuinely used by `alembic/env.py`.
- `packages/knowledge/`'s loaders, embeddings, splitters, and retrievers that are internally broken (wrong class-name imports, method-signature mismatches) but *would* be reachable if `knowledge_manager`'s wiring were completed — these are tracked as correctness bugs in `docs/BUILD_STATUS.md`, not listed here as "unused," since the intent is clearly for them to be used once finished.
- Anything under `.venv/`, `__pycache__/`, `logs/`, `storage/`, `uploads/`, `temp/` — already correctly gitignored, not tracked.

---

## Suggested cleanup order

1. **Fix the two live-breaking `__init__.py` files first** — `packages/rag/builders/__init__.py` and `packages/rag/pipelines/__init__.py` are currently why the app can't start at all (see `docs/BUILD_STATUS.md`). This isn't optional cleanup, it's the top priority in the repo right now.
2. `git rm packages.zip packages/graph.zip graph.png`, then add `*.zip` and a root-level `graph.png` rule to `.gitignore`. Both zips are now committed to history, not just untracked — this needs an actual cleanup commit.
3. Fix or delete the other three copy-pasted `__init__.py` files (`packages/middleware/`, `packages/planner/`, `packages/memory/implementations/`) before anything tries to import them.
4. Delete `requirements.txt` (or regenerate it from `uv export` if some external process depends on it).
5. Delete `packages/application/` in full, plus `packages/conversation/store.py` and `memory_store.py`.
6. Delete `packages/sdk/upload/`, `packages/sdk/notification/`, `packages/sdk/common/models.py` — or fix their import bugs first if the SDK is meant to be used soon; as-is they're both unused *and* broken.
7. Delete `packages/infrastructure/ai/factory.py` and the `registry` provider in `packages/infrastructure/container/ai.py` (plus its now-unused import of `LLMRegistry`).
8. Decide `packages/rag/pipeline.py`/`packages/rag/retriever.py`'s fate — delete if `packages/rag/pipelines/retrieval.py` is the intended long-term path.
9. Decide `packages/graph/nodes.py` vs `packages/graph/nodes/`'s fate — finish the refactor (update `packages/graph/builder.py` to use the new per-class nodes, then delete `nodes.py`) or delete the new `nodes/` directory until the migration is ready. See `docs/BUILD_STATUS.md` — this is the other half of the current app-breaking outage.
10. `packages/knowledge/` remains the one item here worth finishing rather than deleting — real, substantial work with a coherent architecture; see `docs/BUILD_STATUS.md`'s priority list for what's left.
