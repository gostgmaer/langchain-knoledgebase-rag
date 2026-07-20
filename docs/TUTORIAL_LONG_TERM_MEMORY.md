# Tutorial: Building Real Long-Term Memory for an AI Agent

This walks through what was actually built to make this app's AI remember things about a user across *separate conversations* — not just within one chat session. It's written to teach the concepts, not just list the changes (see [`docs/CHANGELOG.md`](./CHANGELOG.md) for that).

---

## 1. Two kinds of "memory," and why they're different problems

There are two completely different things people mean by "the AI remembers":

**Short-term (conversation) memory** — within *one* conversation, the AI can see what was said earlier in that same thread. This is easy: you just re-send the whole message history (or a summary of it) as part of the prompt on every turn. This app already had this working — `ConversationContextBuilder` loads a conversation's messages from the database and feeds them back in.

**Long-term memory** — the AI recalls facts about you *in a brand-new conversation* that has no message history at all. This is the hard problem, and it's what this tutorial covers. It requires three separate capabilities working together:

1. **Extraction** — after a conversation turn, decide what's actually worth remembering (not "hello", but "I prefer Rust" or "I'm building a startup called Ferrolabs").
2. **Storage** — save that fact somewhere durable, indexed in a way that lets you find it again later by *meaning*, not just by exact keyword match.
3. **Retrieval** — at the start of a *different* conversation, search that storage for anything relevant to what's being discussed now, and inject it into the prompt.

---

## 2. Why "the code exists" doesn't mean "it works"

Before touching anything, the existing code was traced end to end, and it revealed a very common trap: **a pipeline that runs cleanly from top to bottom, produces no errors, and does absolutely nothing.**

```python
# packages/memory/implementations/postgres_store.py — before
async def create(self, request: CreateMemoryRequest) -> MemoryFact:
    memory = MemoryFact(id=uuid4(), ...)   # builds a Python object
    # INSERT INTO memories ...              # ...and this comment is the entire "implementation"
    return memory                           # hands back an object nothing ever saved
```

This is a **stub that looks like a real function**. It has the right signature, the right type hints, it doesn't raise an exception — and it throws away everything it's given. The retrieval side had a subtler version of the same problem: it *did* run a real database query, but against the wrong table (the RAG document search index, not a memories table), so it would always come back empty even if something had been stored.

**Lesson:** when auditing whether a feature "works," reading the code isn't enough. You have to trace what happens to the data — does it actually reach a database, and does whatever reads it later query the *same* place?

---

## 3. Designing the storage layer

To make extraction findable later by *meaning* rather than exact words, you don't store plain text and search with `LIKE '%rust%'`. You convert the text into a vector (a long list of numbers — 3072 of them, in this case) using an embedding model, store that vector alongside the text, and later convert your *search query* into a vector the same way. Then "similar meaning" becomes "vectors that point in a similar direction" — measured with cosine distance. This is the same core idea RAG document search already uses in this codebase; memory just needed its own copy of it.

### 3a. The table

```python
# packages/domain/models/memory.py
class Memory(BaseModel):
    __tablename__ = "memories"

    tenant_id: Mapped[UUID]                      # who this belongs to
    user_id: Mapped[UUID | None]
    conversation_id: Mapped[UUID | None]          # where it came from (nullable — a memory can outlive the conversation)

    type: Mapped[MemoryType]                      # fact / preference / project / goal / skill / profile / task / summary
    content: Mapped[str]                           # the actual text, e.g. "User prefers Rust."
    importance: Mapped[float]

    vector: Mapped[list[float]] = mapped_column(
        Vector(settings.embedding.dimensions),     # the pgvector column — this is what makes semantic search possible
    )
```

`Vector` comes from the `pgvector` Postgres extension (already used elsewhere in this codebase for `model_profiles.vector`). It's just a Postgres column type that knows how to store a fixed-length array of floats efficiently and — crucially — provides distance operators you can `ORDER BY` directly in SQL.

### 3b. The repository — the actual search query

```python
# packages/infrastructure/repositories/memory.py
async def search_similar(self, *, tenant_id, query_vector, user_id=None, k=5) -> list[Memory]:
    stmt = select(Memory).where(Memory.tenant_id == tenant_id)
    if user_id is not None:
        stmt = stmt.where(Memory.user_id == user_id)

    stmt = stmt.order_by(
        Memory.vector.cosine_distance(query_vector)   # <- the whole trick
    ).limit(k)

    return await self.scalars(stmt)
```

`.cosine_distance(query_vector)` is a method pgvector-sqlalchemy adds to any `Vector`-typed column. Ordering by it means "give me the rows whose stored vector is closest in *meaning* to my query vector" — this single line is doing the actual semantic search, entirely inside Postgres, no extra vector database needed.

### 3c. Wiring it together

Three layers, each with one job:

- **`MemoryRepository`** — raw database access (the code above). Doesn't know anything about embeddings or LLMs.
- **`PostgresMemoryStore`** — implements the `MemoryStore` interface. Its job is to turn a `CreateMemoryRequest` into an embedded, saved row: call `EmbeddingManager.aembed_query(content)` to get the vector, then hand the row to the repository.
- **`PgVectorMemoryRetriever`** — implements `MemoryRetriever`. Same embedding step, but for a search query instead of content being saved, then calls `search_similar()`.

```python
# packages/memory/implementations/postgres_store.py — after
async def create(self, request: CreateMemoryRequest) -> MemoryFact:
    row = MemoryRow(
        tenant_id=request.tenant_id,
        content=request.content,
        vector=await self._embed(request.content),   # <- the real work, now actually happening
        ...
    )
    row = await self._repository.create(row)          # <- and actually persisted
    return self._to_fact(row)
```

This is the general pattern worth remembering: **domain model → repository (SQL) → store/retriever (business logic + embedding) → manager (orchestration) → graph node (when it runs)**. Each layer only knows about the one below it.

---

## 4. Where this plugs into the actual conversation

Two LangGraph nodes touch memory, one at each end of a turn:

```python
# packages/graph/nodes/load_memory.py — runs BEFORE the LLM
async def __call__(self, state):
    query = state["messages"][-1].content
    response = await self._memory.search(SearchMemoryRequest(query=query, tenant_id=..., user_id=...))
    state["memories"] = [result.memory for result in response.results]
    return state
```

```python
# packages/graph/nodes/extract_memory.py — runs AFTER the LLM responds
async def __call__(self, state):
    await self._memory.extract(conversation_id=..., tenant_id=..., user_id=..., messages=state["messages"])
    return state
```

`LoadMemoryNode` searches for anything relevant to the *current* message and stuffs it into `state["memories"]`, which `PromptBuilder` later folds into the system prompt so the LLM sees it as context. `ExtractMemoryNode` runs after the response is generated, asking a separate LLM call "what from this exchange is worth remembering long-term," and saves whatever it decides.

---

## 5. Three bugs, three lessons — found only by actually testing it

Writing the code above was maybe 40% of the work. Getting it to actually persist and retrieve correctly took three more rounds of "run it for real, see what breaks."

### Bug 1 — the embedding dimension didn't match the real model

```
sqlalchemy.exc.DBAPIError: expected 1536 dimensions, not 3072
```

The `vector` column was created using `settings.embedding.dimensions`, which defaulted to `1536` — a very common size (OpenAI's older embedding models use it). But the model actually configured (`gemini-embedding-001`) produces `3072`-dimensional vectors. Nothing in the code was "wrong" in isolation; the *config value* just didn't describe reality.

**Lesson:** a config default is a claim about the outside world, not just a number. It needs to match whatever you're actually calling, and the only way to know for sure is to trigger the real call and look at what comes back — reading documentation or assuming based on a similar-sounding model name isn't reliable enough for something like a fixed-width database column.

### Bug 2 — Postgres enums don't auto-update

```
asyncpg.exceptions.InvalidTextRepresentationError: invalid input value for enum memorytype: "PROJECT"
```

The `MemoryType` enum was extended in Python (added `GOAL`, `SKILL`, `PROJECT`), but Postgres had already created its own `memorytype` enum *type* the first time the table was made, with only the original 5 values baked in. Python enums and Postgres enum types are two separate things that happen to be kept in sync by SQLAlchemy *only at creation time* — adding a Python value later doesn't retroactively add it to the database.

```sql
ALTER TYPE memorytype ADD VALUE 'PROJECT';
```

**Lesson:** anything backed by a database schema has *two* places it can drift out of sync: the code, and the already-existing structure the code assumes exists. `CREATE TYPE` and `ALTER TYPE` are different operations, and ORMs generally only run the first one automatically.

### Bug 3 — the real one: a cache that outlived its own assumptions

This one didn't throw an error at all, which is exactly what made it dangerous. Memories appeared to save successfully (no exception), but querying the table directly afterward showed **zero rows**. Nothing was visibly broken; the feature just silently didn't work.

The cause was a dependency-injection lifecycle mismatch. This app uses two provider lifetimes:

- **`Singleton`** — built once, the first time anything asks for it, then that exact same instance is reused forever.
- **`Factory`** — built fresh, every single time something asks for it.

`GraphManager` (and everything inside it — the LangGraph nodes, including `ExtractMemoryNode`) was wired as `Singleton`. That's normally a reasonable choice for something like "the compiled graph structure," which doesn't change between requests. But this graph's nodes *transitively* depend on a database session — and this app deliberately gives every HTTP request its own fresh session (so two requests don't corrupt each other's in-flight transactions), opened right when the request starts and committed right when it ends.

Here's the collision: the very *first* time anything touched `container.graph.builder()` in this app's life was at startup, in `lifespan.py`, rendering a `graph.png` diagram — **before any HTTP request, and therefore before any request-scoped session, existed.** Building the Singleton at that moment meant every node inside it permanently captured whatever session existed *then* — some standalone session with no request attached to it, that nothing would ever call `.commit()` on.

Every memory-extraction write after that point was technically succeeding — `INSERT` really did run, inside that one session's own pending transaction — but it was a transaction nobody would ever commit, invisible to every other connection until the process exits and the whole thing rolls back.

```python
# packages/infrastructure/container/graph.py — the fix
# Before: providers.Singleton — built once, forever
# After:
extract_memory = providers.Factory(
    ExtractMemoryNode,
    memory_manager=memory.manager,
)
# ...and everything else in the chain (nodes, builder, manager, MemoryManager itself)
```

Switching the whole chain to `Factory` means it's rebuilt fresh every time it's resolved — which, because of how the request-scoping mechanism works, only ever happens *inside* an active request, after that request's session is already set up correctly.

**Lesson:** dependency-injection lifetimes aren't just a performance knob. `Singleton` implicitly means "whatever this depends on, capture it once and never look again" — which is exactly wrong for anything that's supposed to be scoped to a request. The bug doesn't announce itself with an error; it just makes the data invisible, which is much harder to notice than a crash. When something "works" with no output but no visible effect either, that's the pattern to be suspicious of.

---

## 6. Proving it, properly

The easy, wrong way to "test" this would be: send a message, then ask a follow-up in the *same* conversation, and see if it remembers. That would pass even with zero long-term memory working at all — because ordinary conversation history (section 1) already explains that recall on its own.

The test that actually isolates long-term memory has to remove every other explanation:

```python
conv1 = create_conversation()
conv2 = create_conversation()   # a second, completely unrelated conversation

chat(conv1, "My favorite language is Rust, I'm building a startup called Ferrolabs.")

response = chat(conv2, "What do you know about my preferences and my company?")
# conv2 has ZERO message history — if it knows anything, it can only have come
# from long-term memory search, nothing else
```

And then, not trusting even that — going straight to the database to confirm real rows exist with the right content:

```sql
SELECT type, content, importance FROM memories ORDER BY created_at DESC;
--  PREFERENCE | User prefers using Rust for development.
--  PROJECT    | User is the founder of a robotics startup called Ferrolabs.
```

**Lesson:** when testing whether persistence works, design the test so that the *only* possible explanation for a correct answer is the thing you're trying to prove. If there's an easier explanation available (like same-conversation history), a passing test doesn't actually tell you what you think it does.

---

## Where the pieces live, for reference

| Piece | File | Job |
|---|---|---|
| Table | `packages/domain/models/memory.py` | Schema + the `pgvector` column |
| Repository | `packages/infrastructure/repositories/memory.py` | Raw SQL, including the similarity search |
| Store | `packages/memory/implementations/postgres_store.py` | Embed + persist (create/update/delete/get) |
| Retriever | `packages/memory/implementations/pgvector_retriever.py` | Embed + search |
| Orchestrator | `packages/memory/manager.py` | Ties store/extractor/summarizer/retriever together |
| Extraction | `packages/memory/implementations/llm_extractor.py` | Asks an LLM what's worth remembering |
| Graph nodes | `packages/graph/nodes/{load_memory,extract_memory}.py` | Where this runs inside a chat turn |
| DI wiring | `packages/infrastructure/container/{memory,graph}.py` | How all of the above get constructed — and where the `Singleton`/`Factory` lesson lives |
