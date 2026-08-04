# EasyDev AI Platform

A production-oriented, multi-tenant RAG (Retrieval-Augmented Generation) platform: a FastAPI backend orchestrated with LangChain/LangGraph, a Next.js admin/chat frontend, and a document-ingestion pipeline backing real hybrid + self-query + parent-document + multi-vector retrieval — not a tutorial project.

## What's actually built

This isn't a feature wishlist — every item below is implemented and live-verified against a running instance. The authoritative, continuously-reverified account is [`docs/BUILD_STATUS.md`](./docs/BUILD_STATUS.md); [`docs/mvpRAG.md`](./docs/mvpRAG.md) is the target roadmap it's checked against.

- **Chat**, streaming and non-streaming, with persistent multi-turn memory (short-term via conversation history, long-term via a real per-user fact store with semantic recall across separate conversations).
- **Retrieval-Augmented Generation**: document ingestion (PDF/DOCX/TXT/Markdown/HTML/CSV/JSON), chunking (recursive/markdown-aware/semantic), and multiple real retrieval strategies — similarity, MMR, hybrid (dense + BM25 via reciprocal rank fusion), self-query (LLM-extracted metadata filters), parent-document (small-chunk precision, full-section context), and multi-vector (document-level summary representations).
- **Tool calling with Human-in-the-Loop approval** — every tool call pauses for explicit approve/reject via LangGraph's `interrupt()`/`Command(resume=...)`, backed by a real Postgres checkpointer so a pending approval survives across separate HTTP requests.
- **Multi-tenant** throughout (tenant/user scoping on every table and query), with dynamic feature flags and RBAC gating.
- **Production concerns that are actually wired in**: circuit breakers, retry with backoff, rate limiting, per-tenant token usage and cost tracking, OpenTelemetry tracing, structured logging, background job processing (arq) for ingestion/cleanup/re-indexing/crash recovery.
- **Durable execution** — a crash mid-turn is detected and automatically recovered by a background sweep, not silently lost.
- A real `pytest` suite (unit/integration/workflow/API tiers) and an admin dashboard (analytics, usage, feature flags) in the frontend.

## Stack

- **Backend**: FastAPI, LangChain, LangGraph, SQLAlchemy (async) + PostgreSQL with `pgvector`, Redis, Chroma (vector store), `arq` (background jobs), `dependency-injector` (DI).
- **Frontend**: Next.js, TanStack Query, Tailwind.
- **Package management**: [`uv`](https://docs.astral.sh/uv/) for Python (`pyproject.toml` + `uv.lock`); `pnpm`/`npm` for the frontend.

## Quickstart

```bash
cp .env.example .env   # fill in real values — see the file's own comments
uv sync
uv run uvicorn packages.api.app:app --host 127.0.0.1 --port 8000
```

You'll need a running Postgres (with `pgvector`) and Redis — either run them yourself and point `.env` at them, or use the bundled Docker Compose stack:

```bash
docker compose --profile full up -d
```

For a guided, real-command walkthrough (chat, document upload, retrieval, tool approval) see [`docs/QUICKSTART.md`](./docs/QUICKSTART.md). For how the pieces fit together, see [`docs/ARCHITECTURE_TUTORIAL.md`](./docs/ARCHITECTURE_TUTORIAL.md).

There's also a CLI for exercising the system without a frontend:

```bash
uv run python cli.py
```

## Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

## Tests

```bash
uv run pytest              # unit + integration + workflow + API tiers, real Postgres/Redis
uv run pytest -m live      # also exercises a real LLM call — costs real API quota, opt-in only
uv run ruff check packages/
```

## Documentation

| Doc | What it covers |
|---|---|
| [`docs/mvpRAG.md`](./docs/mvpRAG.md) | The target roadmap — what's in scope, in which version, and why. |
| [`docs/BUILD_STATUS.md`](./docs/BUILD_STATUS.md) | The reality check — what's actually built, working, or still open, re-verified against the running app. |
| [`docs/QUICKSTART.md`](./docs/QUICKSTART.md) | A hands-on walkthrough with real commands and real responses. |
| [`docs/ARCHITECTURE_TUTORIAL.md`](./docs/ARCHITECTURE_TUTORIAL.md) | How the system is put together. |
| [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md) | Running the full stack with Docker Compose. |
| [`docs/EXTENDING.md`](./docs/EXTENDING.md) | Adding a new tool, LLM provider, document loader, or DI-wired service. |

## Project layout

```
packages/
  api/            FastAPI app, routers, middleware, dependencies
  application/    Application-layer services (chat, conversations, messages)
  graph/          The LangGraph state machine — nodes, router, builder
  knowledge/      Document loaders, splitters, retrievers, ingestion pipeline
  domain/         SQLAlchemy models and enums
  infrastructure/ Repositories, the DI container, external clients
  worker/         Background jobs (arq)
  config/         Typed, env-backed settings per subsystem
frontend/         Next.js app
tests/            pytest suite (unit / integration / workflow / api)
docs/             Roadmap, status, and how-to documentation
```
