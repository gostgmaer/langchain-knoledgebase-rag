# Testing & Debugging Playbook

There is currently **zero automated test coverage** in this codebase (`docs/BUILD_STATUS.md`, Phase 15 — 0/4). This playbook is the closest thing to a test plan that exists today: a manual verification checklist covering every real subsystem, plus a diagnostic procedure for the one class of failure this project has actually hit in production-like use — an LLM hallucination that survives its own code fix because it got captured as persistent state.

Treat §1 as what a real `pytest` suite should eventually automate (each numbered check maps cleanly to one integration test); treat §2 as what to reach for when something is *behaving* wrong even though the code looks right.

---

## 1. Manual verification checklist

Run these in order against a locally running server (`docs/QUICKSTART.md` has the exact commands for most of these — this section is the checklist form, cross-referenced back to it).

### 1.1 Core chat
- [ ] `POST /api/v1/chat` with no `conversation_id`/no tenant headers → `200`, a coherent response, and a conversation auto-provisioned via `ensure_default_agent`/`ensure_default_conversation`.
- [ ] Same conversation, second message → the response correctly references the first turn's content (proves message history / `ConversationContextBuilder` is real, not per-request-stateless).
- [ ] `POST /api/v1/chat` with an unknown `conversation_id` (a real UUID that just doesn't exist yet) → `200`, and a **new** conversation is created under that exact ID — not a `404`. Confirm via `SELECT id FROM conversations WHERE id = '<uuid>';` that exactly one row exists. This changed by request; the old behavior (404 on an unknown ID) is no longer correct.
- [ ] Time-to-first-token / response time: `planner` and `load_memory` now run concurrently (`packages/graph/builder.py`'s `START` fan-out + `join` node), and memory extraction/summarization runs as a background task after the response, not before it. A plain no-retrieval message should return in a few seconds, not 7-8+.

### 1.2 Retrieval / RAG (`docs/QUICKSTART.md` §1–5)
- [ ] Upload a document with a distinctive, made-up product code → `202`, then background ingestion completes (`Background ingestion finished` in logs, nonzero `chunk_count`). Response's `data.file_id` should be a real UUID from the Upload Service, not a locally-generated placeholder — cross-check it against `SELECT file_id FROM documents WHERE id = '<document_id>';`, should match exactly.
- [ ] Confirm the Upload Service actually received the file (its own logs, or its file-listing endpoint if you have one) — this is the durable copy now; the app's local `storage/temp/` scratch copy should be gone within a few seconds of ingestion finishing.
- [ ] If `UPLOAD_SERVICE_URL` in `.env` is misconfigured or the service is down, the upload request itself should fail with a `502` and a clear message naming `UPLOAD_SERVICE_URL` — **not** a silent fall-back to local-only storage, and not a generic 500.
- [ ] Upload a `.txt` file against the real Upload Service (`https://fms.easydev.in`) → expect a clean `400` with `"File type text/plain not allowed"`, not a `502` or a stack trace — the real service maintains its own MIME allowlist and rejects plain text; this is expected behavior, not a bug to chase.
- [ ] **Tenant isolation, critical**: upload with a distinct `X-Tenant-ID`, then (directly against the Upload Service, or via `container.upload.client().files.list_files(tenant_id=..., ...)`) confirm the file shows up when listing that exact tenant and does **not** show up when listing with no tenant filter (which falls back to the service's own default tenant). If it shows up under the default tenant instead of the real one, `tenant_id` isn't being passed through — this was a real, previously-shipped bug (see `docs/CHANGELOG.md`).
- [ ] Ask about that exact product → correct answer, non-empty `citations`, `citations[0].document_id` matches the uploaded document.
- [ ] Ask a pronoun-only follow-up ("what about its X?") in the same conversation → correctly resolves without restating the product name (proves `QueryAnalyzer`'s rewriting is real, not the keyword-only fallback).
- [ ] Ask about something with no matching document → `citations: []`, and the response explicitly says nothing was found — **not** a claim about "searching public records" or the model's own statelessness (see §2 below if this fails).
- [ ] Ask a plain conversational message ("thanks!") → `citations: []` **and check the planner's `needs_retrieval` decision skipped retrieval entirely**, not just that retrieval ran and found nothing — these are different failure modes with different root causes.
- [ ] Re-upload the exact same file → response shows `skipped: true` behavior (checked via logs, since the upload endpoint itself doesn't expose this — see `IngestionPipeline.ingest()`'s checksum check).

### 1.3 Long-term memory (`docs/QUICKSTART.md` §6)
- [ ] Tell the assistant a fact in conversation A.
- [ ] Ask about that fact in a **genuinely separate** conversation B, same tenant/user → correctly recalls it.
- [ ] Confirm via direct DB query that a real row exists: `SELECT type, content FROM memories WHERE user_id = '<uuid>';`
- [ ] Ask "do you have persistent memory / a knowledge base?" → should describe both capabilities accurately (per the system prompt in `packages/conversation/bootstrap.py`), never claim to be stateless or session-only. **This exact question is the canary for the hallucination-loop failure mode — see §2.**
- [ ] **Memory extraction shouldn't block the response.** Extraction/summarization now runs as a background task after the response is sent (`packages/api/routers/chat.py::_extract_memory_in_background`), not as a graph node — `POST /api/v1/chat` should return as soon as the reply is ready, not after two more LLM calls. Check server logs a few seconds *after* the response arrives for the extraction/summarization to actually complete.
- [ ] **Race-condition regression check**: fire 2-3 messages at the *same* conversation in quick succession (not simultaneously — just fast, like a real user typing quickly) → no `sqlalchemy.exc.MultipleResultsFound` in the logs, and `SELECT COUNT(*) FROM memories WHERE conversation_id = '<uuid>' AND type = 'summary';` stays at exactly 1.

### 1.4 Tool calling
- [ ] Ask the assistant to list its tools → should name exactly the six registered ones (`get_weather`, `get_news`, `get_google_search`, `calculator`, `search_knowledge_base`, `search_document`) — no more, no less. Naming anything else is a hallucination, not a real capability (`docs/BUILD_STATUS.md`'s "10th bug" — `bind_tools()` not being called was the root cause the one time this happened for real).
- [ ] Ask it to compute something via the calculator → confirm the *tool* did the math (check logs for `Calculator Tool Invoked`/`Calculation Successful`), not the LLM guessing.
- [ ] Ask for the weather somewhere → confirm a real `GET api.openweathermap.org` call in logs, with plausible, specific numbers (not a suspiciously round or generic answer).
- [ ] Explicitly ask it to search the knowledge base / a specific document mid-conversation (distinct from the automatic retrieval a normal question triggers) → confirm `search_knowledge_base`/`search_document` get invoked, not just the always-on `retrieve` node. Check `tool.args` on either (`packages/tools/builtin/knowledge_base.py`) if in doubt — should show only `query`(/`document_id`), never `tenant_id`/`model_profile_id`/`state`.

### 1.5 Streaming
- [ ] `POST /api/v1/chat` with `"stream": true` → SSE `token` events arrive progressively, followed by exactly one `done` event.
- [ ] After the stream completes, `GET /api/v1/conversations/{id}/messages` (or ask a follow-up) → confirm the full assembled text was persisted as **one** message, not duplicated or truncated.
- [ ] Confirm tool-calling and retrieval both still work over the streaming path, not just the non-streaming one — these have regressed independently of each other before.

### 1.6 Session management
- [ ] `GET /api/v1/conversations/{id}` → returns the conversation's metadata; a wrong tenant or nonexistent ID both `404`.
- [ ] `GET /api/v1/conversations/{id}/messages` → returns the full history, oldest-first, matching what was actually sent/received; try `limit`/`offset` to confirm pagination.
- [ ] Check the startup log for `Persistent (Postgres-backed) checkpointer ready.` — should say this on every platform, including native Windows (`ThreadedPostgresSaver` sidesteps the uvicorn/psycopg-async incompatibility, see `docs/ARCHITECTURE_TUTORIAL.md` §13). `Could not set up persistent checkpointer, falling back to in-memory` means Postgres is genuinely unreachable — a real problem worth investigating, not an expected platform difference.

### 1.7 Multi-tenancy / auth
- [ ] Same query, two different `X-Tenant-ID` values, one with an uploaded document and one without → the tenant with the document gets a cited answer, the other gets none. (Confirms retrieval filters are actually tenant-scoped, not just accepted and ignored.)
- [ ] A request with a bogus `Authorization: Bearer <garbage>` header → still completes successfully (fail-open), with a log line showing IAM resolution failed and fell back to the default identity.
- [ ] `GET /health` → `{"database": "healthy", "redis": "healthy"}` when both are actually up; flips to `"unhealthy"`/`"degraded"` if you stop either (useful for confirming the healthcheck isn't a fake "always 200").

### 1.8 Import / wiring sanity (cheapest checks, run these first when something's broken)
```python
# Full import sweep — catches syntax errors, missing modules, broken imports across the whole tree
import pathlib, importlib
for path in sorted(pathlib.Path("packages").rglob("*.py")):
    if "__pycache__" in path.parts: continue
    mod = ".".join(path.with_suffix("").parts).removesuffix(".__init__")
    try: importlib.import_module(mod)
    except Exception as e: print(mod, "->", type(e).__name__, e)
```
```python
# Full DI container construction — catches wiring bugs (wrong provider name, circular deps, missing dependency container) instantly, without a real request
from packages.infrastructure.container.application import ApplicationContainer
c = ApplicationContainer()
c.init_resources()
print(type(c.chat_service.chat_service()).__name__)   # should print "ChatService" cleanly
```
As of this project's last full sweep: **~23 pre-existing import failures**, all in confirmed-dead packages (`packages/sdk/upload/`, `packages/sdk/notification/`, etc. — see `docs/UNUSED_FILES.md`). Any *new* failure outside that known set is a real regression, worth investigating before anything else.

---

## 2. Troubleshooting: "the assistant is denying a capability it actually has"

This is a real, previously-hit failure mode, not a hypothetical — the assistant confidently claiming "I have no persistent memory" or "I have no knowledge base, I only work within this session" when both are genuinely implemented and working. It has two distinct possible root causes, and they require different fixes. Work through them **in this order** — later steps are more invasive and shouldn't be reached for until earlier ones are ruled out.

### 2.1 First: is it actually a code bug, right now?

Reproduce the exact question in a **brand-new conversation** (no `conversation_id`, a `user_id` you've never used before):

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: <tenant>" -H "X-User-ID: $(uuidgen)" \
  -d '{"message": "Do you have a persistent knowledge base and memory?"}'
```

If this **also** gives the wrong answer → it's a real, current code bug. Check, in order:
1. `packages/conversation/bootstrap.py`'s `ensure_default_agent()` — does the seeded `system_prompt` actually describe both capabilities? (It should explicitly say "not just for the current session" and "do not default to generic claims of statelessness" — if that language is missing, this is the bug.)
2. `packages/prompts/builder.py`'s `PromptBuilder.build()` — is retrieved context/memory being folded into the system message correctly, or reintroduced as separate `"human"` turns? (The latter causes the model to misattribute retrieved content as something the *user* said — a real, previously-fixed bug; check for the `sections = [system_prompt]` / single-system-message pattern.)
3. Is retrieval/memory-loading actually running for this query? Add a temporary log line in `RetrieveNode.__call__`/`LoadMemoryNode.__call__` and confirm they're reached.

### 2.2 If a brand-new conversation gives the *correct* answer — it's poisoned state, not code

This is the more insidious case, and it's the one this project actually hit. If the bug only reproduces in one specific, long-lived conversation, the code is fine — **the data is the problem**. Two places to check, both scoped to the specific `tenant_id`/`user_id` in question:

**Poisoned conversation history.** A long-lived conversation accumulates the model's own earlier wrong self-descriptions as prior assistant turns; the model then stays "consistent" with its own past mistakes on every later turn in that same thread, regardless of how correct the current prompt logic is.

```sql
SELECT id, session_id, created_at FROM conversations WHERE tenant_id = '<tenant>' AND user_id = '<user>';
SELECT role, content, created_at FROM messages WHERE conversation_id = '<the suspect one>' ORDER BY created_at;
```
Look for old assistant messages claiming statelessness/no-memory. If found, the fix (with the user's explicit sign-off — this is destructive) is:
```sql
DELETE FROM messages WHERE conversation_id = '<the suspect one>';
```

**Poisoned long-term memory — check this even if the conversation history looks clean, since memory is recalled across *every* conversation for that user, not just the one you're looking at.**

```sql
SELECT id, type, content FROM memories WHERE tenant_id = '<tenant>' AND user_id = '<user>' ORDER BY created_at;
```
Look specifically for `FACT`-typed rows that are actually the model's own capability claims (`"The AI operates on a session-based memory model..."`, near-duplicated many times with minor wording variations) or anything that looks fabricated rather than genuinely user-supplied (a plausible-sounding but invented association between a product code and a real company, for instance). If found:
```sql
DELETE FROM memories WHERE tenant_id = '<tenant>' AND user_id = '<user>';
```
This deletes *all* memory for that user, including legitimate facts — acceptable for a dev/test tenant; for anything resembling real user data, filter to just the poisoned rows by `id` instead of wiping the whole set.

**After cleanup**, re-run the exact same query in the exact same (now-cleaned) conversation and confirm the answer is correct — don't just assume the `DELETE` worked.

### 2.3 The actual root cause, if you want to fix this class of bug for good

`packages/memory/implementations/llm_extractor.py`'s extraction prompt has no instruction excluding the model's own self-referential claims from being captured as durable facts. Any wrong answer the model gives about its own capabilities is exactly as eligible for extraction as a real fact about the user — and once extracted, it's self-reinforcing, since every future turn recalls it as ground truth. This is a known, currently open gap (`docs/BUILD_STATUS.md`'s priorities list) — fixing it means adding an explicit exclusion to `_EXTRACTION_PROMPT` (something like *"Do not extract claims about your own capabilities, memory, or knowledge base — only extract facts about the user, their preferences, or their work"*) and, ideally, a regression test that feeds a conversation containing a wrong self-description through the extractor and asserts nothing gets captured from it.

---

## 3. General debugging habits worth adopting from this project's own history

- **Prove it live, not just "the code looks right."** Nearly every real bug found in this project's development was found by actually running a request and checking the response/logs/database, not by code review alone — a wrong `settings.field` name, a Singleton capturing a stale session, a provider never passing its API key all *look* correct in isolation.
- **A `200 OK` is not proof of correctness.** Several real bugs in this project's history produced perfectly well-formed, plausible-sounding, *wrong* responses (hallucinated tool names, a fabricated product-brand association, a confident "I have no memory" from a system that does). Read the actual response content, not just the status code.
- **When something regresses after a fix that should have solved it, check the data before re-reading the code.** §2 above is the canonical example — the code fix was correct and verified, but stale data kept producing the old symptom regardless.
