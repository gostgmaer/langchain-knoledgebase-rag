# How to Extend This System

Four concrete "add a new X" walkthroughs, for the four things someone working in this codebase is most likely to need to do. Each one names the exact files to touch, in order, based on the real patterns already in the codebase — not a generic template. See [`docs/ARCHITECTURE_TUTORIAL.md`](./ARCHITECTURE_TUTORIAL.md) if you need to understand *why* a layer is shaped the way it is before extending it.

---

## 1. Add a new tool (something the AI can call mid-conversation)

The existing tools live in `packages/tools/builtin/` — `calculator.py`, `weather.py`, `news.py`, `search.py`. Each is a plain LangChain `@tool`-decorated function; there's no custom base class to subclass.

**Step 1 — Write the tool function.** Follow `packages/tools/builtin/weather.py`'s shape:

```python
# packages/tools/builtin/currency.py
from langchain.tools import tool
import httpx
from packages.config.loader import settings
from packages.logging.logger import get_logger

logger = get_logger(__name__)
client = httpx.AsyncClient(timeout=10)

@tool(
    "convert_currency",
    description="Convert an amount from one currency to another using live exchange rates.",
    return_direct=False,
)
async def convert_currency(amount: float, from_currency: str, to_currency: str) -> dict:
    """Convert a currency amount using live rates."""
    try:
        response = await client.get(
            f"{settings.tools.exchange_api_url}/convert",
            params={"from": from_currency, "to": to_currency, "amount": amount, "access_key": settings.tools.exchange_api_key},
        )
        response.raise_for_status()
        data = response.json()
        return {"success": True, "tool": "convert_currency", "result": data["result"], "summary": f"{amount} {from_currency} = {data['result']} {to_currency}"}
    except httpx.HTTPError as e:
        return {"success": False, "tool": "convert_currency", "error": str(e)}
```

Two things every tool in this codebase does that are worth keeping: **the docstring/description is what the model reads to decide when to call it** — be specific, the way `calculator.py`'s tool description spells out every supported operator and gives concrete examples; and **return a structured dict, not a bare string**, on success — it's easier for the model to summarize accurately and easier to test.

If the tool needs a new API key/config value, add it to `packages/config/tools.py`'s `ToolsSettings` class (follow `weather_api_key`/`weather_api_url`'s pattern) and to `.env.example`.

**Step 2 — Register it.** Edit `packages/infrastructure/container/tools.py`:

```python
from packages.tools.builtin.currency import convert_currency

def init_tool_manager(registry, executor):
    manager = ToolManager(registry=registry, executor=executor)
    manager.register(get_weather)
    manager.register(get_news)
    manager.register(get_google_search)
    manager.register(calculator)
    manager.register(convert_currency)   # <-- add this line
    return manager
```

That's it — `ToolManager.list()` is what `LLMNode` passes into `bind_tools()` every turn (`packages/graph/nodes/llm.py`), so the moment it's registered here, the model can see and call it. No graph changes needed; `packages/graph/nodes/tool.py`'s `GraphToolNode` wraps LangGraph's generic `ToolNode` over *whatever* `tool_manager.list()` returns.

**Step 3 — Verify.** Start the server and ask the assistant to list its tools — it should now name the new one (confirming `bind_tools()` picked it up), then ask it to actually use it and confirm the live API call happens (check server logs for evidence it's a real call, not a hallucinated answer — this exact class of bug bit this project once already, see `docs/BUILD_STATUS.md`'s "10th bug" entry).

---

## 2. Add a new LLM provider

The four existing providers (`packages/infrastructure/ai/providers/{google,openai,anthropic,groq}.py`) are all tiny — each is only responsible for constructing the underlying LangChain chat model; everything else (`invoke`/`stream`/`bind_tools`/`with_structured_output`) is inherited from `BaseProvider` (`packages/infrastructure/ai/providers/base_provider.py`).

**Step 1 — Add the enum value.** `packages/infrastructure/ai/models.py`'s `LLMProvider` enum needs a new member (e.g. `MISTRAL = "mistral"`).

**Step 2 — Write the provider class.**

```python
# packages/infrastructure/ai/providers/mistral.py
from langchain_mistralai import ChatMistralAI
from .base_provider import BaseProvider
from packages.config.loader import settings

class MistralProvider(BaseProvider):
    def _create_model(self):
        return ChatMistralAI(
            model=self.config.model,
            api_key=settings.ai.mistral_api_key,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
```

That's the entire class — `self.config` is the `LLMConfig` dataclass (`packages/infrastructure/ai/config.py`) already populated with `model`/`temperature`/`max_tokens`/`top_p`/`top_k` from settings; `_create_model()` just needs to map those onto whatever constructor arguments the target LangChain integration expects. **Read the API key from `packages.config.loader.settings`, not `os.environ` directly** — this codebase had a real, live bug once (`GoogleProvider` never passing `api_key=` at all, silently working only because of an unrelated `load_dotenv()` side effect elsewhere) that a wrong-source api key would resemble.

**Step 3 — Wire it into the factory.** `packages/infrastructure/ai/providers/factory.py`'s `LLMFactory.create()`:

```python
match config.provider:
    case LLMProvider.GOOGLE:
        return GoogleProvider(config)
    ...
    case LLMProvider.MISTRAL:
        return MistralProvider(config)
```

**Step 4 — Add the settings field.** `packages/config/ai.py`'s `AISettings` needs `mistral_api_key`, and `.env.example` needs a documented `MISTRAL_API_KEY=` line.

**Step 5 — Select it.** Set `AI_DEFAULT_PROVIDER=mistral` in `.env` (`packages/infrastructure/ai/config.py`'s `get_default_llm_config()` reads `settings.ai.default_provider` and does `LLMProvider(...)` on it — a typo here raises `InvalidProviderError` at the first LLM call, not at startup, so double-check the string matches the enum's value exactly).

**Verify live**, not just "it imports" — this codebase's own history has four separate passes of a provider looking correct in source but never being exercised with a real key. Send a real chat message and confirm a genuine API call reaches the new provider (check for its distinctive response shape/error messages if the key is wrong, rather than assuming success from a 200 that might be falling back to a different configured provider).

---

## 3. Add a new document loader (support a new file type)

**Step 1 — Write the loader.** Follow `packages/knowledge/loaders/text.py`'s shape — subclass `BaseDocumentLoader` (`packages/knowledge/loaders/base.py`), set `loader_name`, and delegate to a real LangChain community loader via the shared `execute()` helper (which handles path validation, logging, metadata normalization, and wrapping failures in `DocumentReadError`):

```python
# packages/knowledge/loaders/epub.py
from pathlib import Path
from langchain_community.document_loaders import UnstructuredEPubLoader
from langchain_core.documents import Document
from .base import BaseDocumentLoader

class EpubDocumentLoader(BaseDocumentLoader):
    loader_name = "epub"

    async def load(self, path: Path) -> list[Document]:
        loader = UnstructuredEPubLoader(str(path))
        return await self.execute(path=path, loader=loader)
```

**Step 2 — Register the extension.** `packages/knowledge/loaders/factory.py`'s `LoaderFactory._loaders` dict:

```python
_loaders: dict[str, type[DocumentLoader]] = {
    ".pdf": PDFDocumentLoader,
    ...
    ".epub": EpubDocumentLoader,   # <-- add this line
}
```

That's the whole integration — `DocumentLoaderManager.load()` (`packages/knowledge/loaders/manager.py`) just calls `LoaderFactory.create(path)` and lets the extension-to-class dict do the routing; nothing about `IngestionPipeline` (`packages/knowledge/pipelines/ingestion.py`) needs to change, since it only ever calls the manager, never a concrete loader.

**Step 3 — Verify.** Upload a real file of the new type via `POST /api/v1/documents`, confirm `Background ingestion finished` in the logs with a nonzero `chunk_count`, then ask a question whose answer only exists in that file and confirm a citation comes back pointing at it (same pattern as `docs/QUICKSTART.md`'s Step 1–2, just with your new file type).

---

## 4. Wire a new service into the DI container

This is the one place in the codebase with a real, documented, previously-live bug class attached to it — read this section even if the other three feel routine.

**The rule:** if your new service (transitively) depends on a per-request database session, it **must** be wired as `providers.Factory`, never `providers.Singleton`. A `Singleton` is constructed exactly once — the first time anything touches it, which can happen at app *startup* (`packages/api/lifespan.py`'s `GraphVisualizer.save_png()` call reaches deep into the graph container before any HTTP request ever exists). Every "request" after that silently reuses the one session that existed at that first construction — permanently orphaned, never committed, with no error thrown anywhere. This exact bug has been found and fixed multiple times in this project's history (the memory pipeline, then the document-ingestion pipeline) — the comments in `packages/infrastructure/container/rag.py` and `packages/infrastructure/container/graph.py` explain it directly, in place, precisely so the next person adding a provider doesn't reintroduce it.

**Concrete steps**, using a hypothetical `FeedbackService` that needs a repository:

1. Pick (or create) the right sub-container. Most new domain services belong in `packages/infrastructure/container/services.py` if they're stateless business logic, or get their own file (mirroring `container/rag.py`, `container/memory.py`) if they're a substantial subsystem.
2. Declare the provider:
   ```python
   feedback_service = providers.Factory(   # Factory, not Singleton — it needs repositories.feedback
       FeedbackService,
       repository=repositories.feedback,
   )
   ```
3. If the new sub-container needs another container's providers (e.g. `repositories`, `ai`), declare a `providers.DependenciesContainer()` placeholder for it and pass the real container in when composing it from `packages/infrastructure/container/application.py` — follow exactly how `rag = providers.Container(RAGContainer, settings=settings, ai=ai, services=services, repositories=repositories)` does it.
4. If the new service needs to be reachable from an API route, add a `get_feedback_service()` dependency function to `packages/api/dependencies.py` (mirror `get_memory_manager`'s three-line shape), and use it as `Depends(get_feedback_service)` in the router.
5. **Verify the DI wiring actually resolves**, not just "the file has no syntax errors" — the cheapest real check in this codebase's own history:
   ```python
   from packages.infrastructure.container.application import ApplicationContainer
   c = ApplicationContainer()
   c.init_resources()
   service = c.services.feedback_service()   # or wherever you wired it
   print(type(service).__name__)
   ```
   A provider that's misconfigured (wrong dependency name, circular reference, wrong container composed) throws here, immediately — this has caught real bugs in this project every single time it's been used as a check, faster than waiting for an actual HTTP request to exercise the same path.

**If you're unsure whether something needs `Factory`**, ask: does this class, or anything it depends on (transitively), ultimately hold a reference to a `sqlalchemy.ext.asyncio.AsyncSession`? If yes → `Factory`. If it's genuinely stateless or holds no per-request resource (a config object, an HTTP client, a compiled regex) → `Singleton` is fine and slightly cheaper.
