# Quickstart Walkthrough

A hands-on companion to [`docs/ARCHITECTURE_TUTORIAL.md`](./ARCHITECTURE_TUTORIAL.md) — that document explains *how* the system works; this one proves it, with real commands and real responses from this codebase. Every request/response pair below is a genuine transcript from a live run of this exact app during development (Postgres + the FastAPI server both running locally) — not hypothetical output. Run the same commands yourself and you should see the same shape of result.

> **Before you start:** this needs a running Postgres (with the `pgvector` extension — `packages/api/lifespan.py` creates it automatically via `CREATE EXTENSION IF NOT EXISTS vector`) and the app's own Chroma vector store directory, both wired via `.env` (copy `.env.example`). See [`docs/DEPLOYMENT.md`](./DEPLOYMENT.md) if you want the full Docker Compose stack instead of running Postgres yourself.

```bash
uv sync
uv run uvicorn packages.api.app:app --host 127.0.0.1 --port 8000
```

Everything below uses a fixed tenant/user pair so the same conversation persists across steps — swap in your own UUIDs (or omit the headers entirely to fall back to the built-in defaults) freely.

```bash
TENANT="11111111-1111-1111-1111-111111111111"
USER="22222222-2222-2222-2222-222222222222"
```

---

## Step 1 — Upload a document

Create a small test file with a couple of distinctive, made-up product codes (so you can be certain any answer citing them came from *this* upload, not the model's training data):

```bash
cat > unit9-specs.txt <<'EOF'
Ferrolabs Robotics Product Specification Sheet

Product code: FLX-77Q2
The FLX-77Q2 is a compact warehouse inventory scanner drone used for shelf audits.

Product code: ZBR-9410
The ZBR-9410 delivers a maximum payload capacity of 63 kilograms and a battery life of 11 hours per charge.
It is designed for narrow-aisle warehouse navigation and integrates with the Ferrolabs fleet management console.

General safety notice: all warehouse robots must be inspected quarterly by certified technicians.
EOF

curl -s -X POST http://127.0.0.1:8000/api/v1/documents \
  -H "X-Tenant-ID: $TENANT" \
  -F "file=@unit9-specs.txt"
```

Real response — note it returns immediately (`202`-shaped envelope with `status: PENDING`), *before* embedding work has finished (see `docs/ARCHITECTURE_TUTORIAL.md` §5 for why — ingestion runs as a `BackgroundTasks` job, off the request path):

```json
{
    "success": true,
    "message": "Document accepted for background ingestion.",
    "data": {
        "status": "PENDING",
        "document_name": "unit9-specs.txt"
    },
    "metadata": {},
    "timestamp": "2026-07-21T12:02:30.320958Z"
}
```

Give it a few seconds (a single small file finishes ingestion in well under a second in practice; the server log will show `"event": "Background ingestion finished", "chunk_count": 1`).

## Step 2 — Ask about something that's actually in the document

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "X-User-ID: $USER" \
  -d '{"message": "What is the payload capacity of the ZBR-9410?"}'
```

Real response:

```json
{
    "success": true,
    "message": "Chat completed successfully.",
    "data": {
        "conversation_id": "b0e0b0a5-758b-458c-8a01-e21019634674",
        "response": "The payload capacity of the ZBR-9410 is 63 kilograms.",
        "model": "gemini-3.1-flash-lite",
        "usage": {},
        "citations": [
            {
                "document_id": "74c9a7e8-52dc-4046-8c20-1f026cffca3f",
                "chunk_id": "e0c7f0ab-3b08-405e-a841-ef44ea45f7b3",
                "chunk_index": 0,
                "score": 9.091263771057129
            }
        ]
    },
    "metadata": {},
    "timestamp": "2026-07-21T12:03:10.070115Z"
}
```

Correct answer, and a real citation pointing at the exact document/chunk that answered it — the `score` is the cross-encoder's relevance score for that chunk against your question (see `docs/ARCHITECTURE_TUTORIAL.md` §6.4). Save `conversation_id` for the next step.

## Step 3 — Ask a follow-up with a pronoun, no explicit context

This is the interesting one: it proves the planner's query-rewriting step is real, not just keyword matching (§4.8 of the architecture tutorial).

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "X-User-ID: $USER" \
  -d '{"conversation_id": "b0e0b0a5-758b-458c-8a01-e21019634674", "message": "what about its battery life?"}'
```

Real response — `"its"` correctly resolved to the ZBR-9410 from the prior turn, with zero explicit restatement of the product name:

```json
{
    "success": true,
    "message": "Chat completed successfully.",
    "data": {
        "conversation_id": "b0e0b0a5-758b-458c-8a01-e21019634674",
        "response": "The ZBR-9410 has a payload capacity of 63 kilograms and a battery life of 11 hours per charge.",
        "model": "gemini-3.1-flash-lite",
        "citations": [
            {"document_id": "74c9a7e8-...", "chunk_id": "e0c7f0ab-...", "chunk_index": 0, "score": 7.74}
        ]
    }
}
```

## Step 4 — Ask something with no relevant document at all

Retrieval genuinely runs and comes back empty here — the system doesn't fabricate a "searched the web" narrative for an empty internal knowledge-base lookup (this exact behavior was a real bug, fixed and documented in `docs/CHANGELOG.md`'s hallucination-incident entry):

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "X-User-ID: 66666666-6666-6666-6666-666666666666" \
  -d '{"message": "What is the maximum thrust output of the Zorblax-Quantum9000 hyperdrive engine according to our internal documentation?"}'
```

Real response — zero citations, and an honest "not found in our KB" answer instead of an invented one:

```json
{
    "data": {
        "response": "I have searched your internal documentation and knowledge base, but I could not find any information regarding a \"Zorblax-Quantum9000\" hyperdrive engine. It is possible that this is a fictional item, a very new addition that has not yet been indexed, or that the documentation is under a different name.\n\nIf you have access to a specific document containing this information, please upload it, and I will be happy to extract the details for you.",
        "citations": []
    }
}
```

## Step 5 — A plain conversational message doesn't trigger retrieval at all

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" -H "X-User-ID: $USER" \
  -d '{"conversation_id": "b0e0b0a5-758b-458c-8a01-e21019634674", "message": "Thanks, that is helpful!"}'
```

Real response — the planner (§4.8) correctly classified this as not needing retrieval at all, so it's not just "retrieval ran and found nothing," it never ran:

```json
{
    "data": {
        "response": "You're very welcome! As mentioned, the ZBR-9410 has a battery life of 11 hours per charge. Let me know if you need anything else!",
        "citations": []
    }
}
```

## Step 6 — Long-term memory, across a *separate* conversation

This is the capability most worth proving explicitly, since it's the one the model is most prone to denying if the system prompt/memory pipeline ever regresses (see `docs/ARCHITECTURE_TUTORIAL.md` §13). Start a brand-new conversation (new `conversation_id`, omitted here so one gets auto-created) and tell it something:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" -H "X-User-ID: 88888888-8888-8888-8888-888888888888" \
  -d '{"message": "My favorite language is Rust and I am building a robotics startup called Ferrolabs."}'
```

Then, in a **genuinely separate** conversation for the same user (pass a *different, explicit* `conversation_id`, or just don't reuse the one you got back):

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" -H "X-User-ID: 88888888-8888-8888-8888-888888888888" \
  -d '{"conversation_id": "<a different UUID than step 6a returned>", "message": "What do you know about my programming preferences and my company?"}'
```

Verified real behavior (from this session's development history): the second, separate conversation correctly answers with both facts, pulled from real rows in the `memories` table via pgvector similarity search — not from shared conversation history, since there is none to share. If you want to see the actual stored rows:

```bash
# requires psql access to the configured DATABASE_URL
psql "$DATABASE_URL" -c "SELECT type, content FROM memories WHERE user_id = '88888888-8888-8888-8888-888888888888';"
```

## Step 7 — Streaming

```bash
curl -s -N -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" -H "X-User-ID: $USER" \
  -d '{"conversation_id": "b0e0b0a5-758b-458c-8a01-e21019634674", "message": "And what about the FLX-77Q2?", "stream": true}'
```

Real response — Server-Sent Events, one `token` event per chunk, then a terminal `done` event:

```
data: {"type": "token", "content": "The FL"}

data: {"type": "token", "content": "X-77Q2 is a compact warehouse inventory scanner drone used for shelf audits."}

data: {"type": "token", "content": " The provided documentation does not specify its payload capacity or battery life."}

data: {"type": "done", "conversation_id": "b0e0b0a5-758b-458c-8a01-e21019634674"}
```

Note there's no `citations` event here — that's a known, deliberate gap (`docs/ARCHITECTURE_TUTORIAL.md` §8.3), not a bug you're hitting.

## Step 8 — Tool calling

Retrieval routing and tool routing are independent — confirm the assistant still has real tool access after all the above:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" -H "X-User-ID: $USER" \
  -d '{"message": "What is the weather in Tokyo right now?"}'
```

Real response — a genuine `GET api.openweathermap.org/...` call happened here, not a guess:

```json
{"data": {"response": "The weather in Tokyo is currently 31.49°C with few clouds. It feels like 38.49°C due to the humidity, which is at 75%."}}
```

---

## What you just proved

- Documents you upload are **actually chunked, embedded, and persisted** — not held only for the current session.
- Retrieval is **query-aware**, not just literal-keyword matching — a pronoun-only follow-up correctly resolved to the right product.
- The system **distinguishes "didn't search" from "searched and found nothing"** and describes each honestly.
- Long-term memory **survives across separate conversations** for the same user, via real vector search — not conversation-local context.
- Streaming and tool-calling both work independently of the RAG/memory pipeline.

If you hit different behavior than described here — especially anything resembling "I don't have persistent memory/knowledge base" — check `docs/ARCHITECTURE_TUTORIAL.md` §13 and `docs/TESTING_PLAYBOOK.md`'s troubleshooting section before assuming it's a new bug; it's the known failure mode of this system, and there's a diagnostic procedure for it.
