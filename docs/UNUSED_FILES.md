# Unused / Unnecessary Files

A cleanup inventory for `langchain-knoledgebase-rag`, verified 2026-07-20 (HEAD `7df652d` + uncommitted changes) by tracing actual imports from every real entry point (`main.py`, `cli.py`, `packages/api/app.py`, `packages/worker/main.py`) and the DI container graph — not just grepping for file names. Companion to [`docs/BUILD_STATUS.md`](./BUILD_STATUS.md), which tracks correctness; this tracks what shouldn't be in the repo at all, or isn't reachable by anything that runs.

Confidence levels, in order of how sure this doc is:
- **Confirmed unused** — zero references anywhere outside the file/package itself. Safe to delete.
- **Wired but never consumed** — the DI container constructs it (so it "imports fine" and even instantiates), but nothing downstream ever calls it or uses the provider. Deleting it requires removing its container wiring too.
- **Junk / repo hygiene** — not a code-correctness issue, just doesn't belong in version control.

---

## Junk files — repo hygiene, delete immediately

| File | Why it shouldn't be here |
|---|---|
| `packages/graph/graph.zip` | A committed zip archive containing **compiled `.pyc` bytecode** and stale copies of `packages/graph/*.py` (timestamps from 2026-07-18/19) — looks like an accidental IDE backup, not intentional source. Committing compiled bytecode inside a zip is a real anti-pattern regardless of intent. |
| `packages/infrastructure/repositories/__init__.zip` | Same pattern — a zip snapshot of the entire `repositories/` directory, stale copies of `__init__.py`, `base.py`, `conversation.py`, `document.py`, etc. |
| `graph.png` (repo root) | Generated output from `GraphVisualizer.save_png()` (see `docs/BUILD_STATUS.md`'s recurring blocker on this exact function) — a build artifact, not source. Currently untracked-then-committed at least once; `.gitignore` doesn't exclude it, so it'll keep reappearing every time that buggy code path runs. |

**Fix:** `git rm` all three, and add `*.zip` and `graph.png` (or `*.png` generally, scoped to repo root) to `.gitignore` so they can't be re-committed by accident.

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
| `sdk/upload/*.py` (8 files: `client.py`, `bulk.py`, `exceptions.py`, `files.py`, `uploads.py`, etc.) | Confirmed unused from `packages/` — only referenced from within `packages/sdk/` itself. Also currently broken: `client.py` imports `UploadSettings` from `packages.config.upload`, which doesn't exist (real path: `packages/config/upload_service.py`, real class: `UploadServiceSettings`). |
| `sdk/notification/*.py` (5 files) | Confirmed unused from `packages/`. Also currently broken: requires the `email-validator` package, which isn't installed. |
| `sdk/common/models.py` | Confirmed unused from `packages/` outside `sdk/` itself. Also currently broken: references `Pagination`/`Page`/`Metadata`/`ErrorResponse`/`HealthResponse` as bare names with no class definitions behind them (`NameError` on import). |

---

## Wired but never consumed

These are real classes that the DI container constructs — so they "work" in the sense of importing and instantiating cleanly — but nothing anywhere actually calls a method on them or uses the provider they're assigned to. They show up as reachable in an import sweep, which is why they're easy to miss; the container graph is what actually reveals them as dead.

| Path | Evidence |
|---|---|
| `packages/infrastructure/ai/registry.py` (`LLMRegistry`) | `packages/infrastructure/container/ai.py:16-18` constructs `registry = providers.Singleton(LLMRegistry)` — but `manager = providers.Singleton(LLMManager)` (the only other provider in this container) takes no arguments and never references `registry`. Superseded by `packages/infrastructure/ai/providers/factory.py`, which `LLMManager` actually uses now. |
| `packages/rag/pipeline.py` (`RAGPipeline`) | `packages/infrastructure/container/rag.py:68-72` constructs `pipeline = providers.Singleton(RAGPipeline, retriever=retriever, indexer=indexer)` — but no other provider in the container references `pipeline`. The one that actually gets used, `manager = providers.Singleton(RAGManager, retrieval_pipeline=retriever, ...)` (line 78-84), depends on `retriever` directly, not `pipeline`. |
| `packages/rag/retriever.py` (`RetrievalPipeline` — note: a *different* class from the same-named one actually in use, see below) | Only imported by `packages/rag/pipeline.py` (the dead leaf above) — so this file is only reachable through an already-unconsumed provider. |
| `packages/knowledge/manager.py` (`KnowledgeManager`) and the ~70-file `packages/knowledge/` subsystem behind it | `packages/infrastructure/container/rag.py:56-61` constructs `knowledge_manager = providers.Singleton(KnowledgeManager, ingestion_pipeline=providers.Object(None), embedding_manager=providers.Object(None), retriever_manager=providers.Object(None))` — real dependencies replaced with `None` placeholders, and no other provider consumes `knowledge_manager`. Calling any real method on it (`.ingest()`, `.search()`, etc.) would immediately raise `AttributeError: 'NoneType' object has no attribute ...`. See `docs/BUILD_STATUS.md` for the detailed internal-bug list (this package also has real, separate correctness bugs beyond just being unwired). |

**A naming trap worth flagging explicitly:** there are **two different classes both named `RetrievalPipeline`** — `packages/rag/retriever.py`'s (dead, per above) and `packages/rag/pipelines/retrieval.py`'s (the one actually constructed as the `retriever` provider and used by the live `RAGManager`). Same for `ChatService` — `packages/chat/chat_service.py` (live, used by `RAGManager` via `services.chat`) vs. `packages/application/services/chat_service.py` (dead, see above) are two unrelated classes with the same name. Both collisions make it easy to misjudge what's actually running just by grepping a class name — worth renaming one side of each pair to prevent future confusion, independent of the cleanup itself.

---

## Not included in this list

- `packages/infrastructure/database/migrations.py` fails to import standalone (`AttributeError: module 'alembic.context' has no attribute 'config'`) — this is **expected**, not dead code. It's an Alembic `env.py`-style module that only works inside an active `alembic` CLI invocation; it's genuinely used by `alembic/env.py`.
- `packages/knowledge/`'s loaders, embeddings, splitters, and retrievers that are internally broken (wrong class-name imports, method-signature mismatches) but *would* be reachable if `knowledge_manager`'s wiring were completed — these are tracked as correctness bugs in `docs/BUILD_STATUS.md`, not listed here as "unused," since the intent is clearly for them to be used once finished.
- Anything under `.venv/`, `__pycache__/`, `logs/`, `storage/`, `uploads/`, `temp/` — already correctly gitignored, not tracked.

---

## Suggested cleanup order

1. `git rm packages/graph/graph.zip packages/infrastructure/repositories/__init__.zip graph.png`, then add `*.zip` and a root-level `graph.png` rule to `.gitignore`.
2. Delete `requirements.txt` (or regenerate it from `uv export` if some external process depends on it).
3. Delete `packages/application/` in full, plus `packages/conversation/store.py` and `memory_store.py`.
4. Delete `sdk/upload/`, `sdk/notification/`, `sdk/common/models.py` — or fix their import bugs first if the SDK is meant to be used soon; as-is they're both unused *and* broken.
5. Delete `packages/infrastructure/ai/factory.py` and the `registry` provider in `packages/infrastructure/container/ai.py` (plus its now-unused import of `LLMRegistry`).
6. Decide `packages/rag/pipeline.py`/`packages/rag/retriever.py`'s fate — delete if `packages/rag/pipelines/retrieval.py` is the intended long-term path, since keeping two same-purpose, differently-wired implementations around is exactly what caused the naming confusion documented above.
7. `packages/knowledge/` is the one item here that's worth finishing rather than deleting — it's real, substantial work with a coherent architecture; see `docs/BUILD_STATUS.md`'s priority list for what's left to wire it up for real.
