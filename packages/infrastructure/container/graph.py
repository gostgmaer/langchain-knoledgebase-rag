# Container graph setup
from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator, Sequence
from typing import Any

from dependency_injector import containers
from dependency_injector import providers
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg import Connection
from psycopg.rows import dict_row

from packages.config.loader import settings as app_settings
from packages.graph.builder import GraphBuilder
from packages.graph.manager import GraphManager
from packages.graph.nodes import GraphNodes
from packages.graph.router import GraphRouter
from packages.knowledge.schemas import Citation, SearchResult
from packages.memory.schemas import MemoryFact, MemoryType
from packages.planner.models import Capability, ExecutionPlan, ExecutionStep
from packages.prompts.builder import PromptBuilder
from packages.prompts.system import get_base_system_prompt

from packages.planner.planner import GraphPlanner
from packages.planner.query_analyzer import QueryAnalyzer
from packages.graph.nodes.load_memory import LoadMemoryNode
from packages.graph.nodes.retrieve import RetrieveNode
from packages.graph.nodes.tool import GraphToolNode
from packages.graph.nodes.llm import LLMNode
from packages.graph.nodes.extract_memory import ExtractMemoryNode

# The checkpointer serializes graph state (including every custom type
# that can appear anywhere in GraphState) with msgpack. Unregistered
# types are blocked outright once this allowlist is non-permissive (see
# the NOTE below) — every dataclass/enum reachable from GraphState needs
# to be listed here, not just the ones that happened to trigger a
# warning first.
#
# NOTE: JsonPlusSerializer()'s default allowed_msgpack_modules is the
# sentinel value True ("allow everything, just warn"), and
# .with_msgpack_allowlist() is a no-op whenever the base serializer's
# current mode is already True/False (see its source: it early-returns
# `self` unchanged in that case). So building via
# JsonPlusSerializer().with_msgpack_allowlist([...]) silently does
# nothing — allowed_msgpack_modules must be passed at construction time
# instead for the restriction to actually take effect. This only became
# observable once the checkpointer itself started persisting for real
# (see the checkpointer provider below) — before that, no checkpoint was
# ever actually deserialized, so neither the no-op allowlist nor the
# gaps in it had any visible effect.
_CHECKPOINT_SERDE = JsonPlusSerializer(
    allowed_msgpack_modules=[
        Capability,
        ExecutionStep,
        ExecutionPlan,
        SearchResult,
        Citation,
        MemoryFact,
        MemoryType,
        ("asyncpg.pgproto.pgproto", "UUID"),
    ]
)


def _to_psycopg_dsn(url: str) -> str:
    """
    psycopg (used by PostgresSaver) doesn't understand SQLAlchemy's driver
    suffix (e.g. `postgresql+asyncpg://`) — strip it to a plain
    `postgresql://` DSN.
    """
    return re.sub(r"^postgresql\+\w+://", "postgresql://", url)


class ThreadedPostgresSaver(BaseCheckpointSaver):
    """
    Wraps LangGraph's official *synchronous* `PostgresSaver`, running
    every call in a worker thread via `asyncio.to_thread()`, instead of
    using the library's own `AsyncPostgresSaver` (psycopg async mode).

    Why: psycopg's async connections refuse to run under Windows'
    default `ProactorEventLoop`, and `uvicorn` hardcodes exactly that
    loop on native Windows regardless of any event-loop policy set at
    the application level (confirmed by reading
    `uvicorn.loops.asyncio.asyncio_loop_factory`'s source) — so
    `AsyncPostgresSaver` can never activate there at all. Plain
    *synchronous* psycopg connections have no such restriction — they
    don't participate in the event loop, they just block whatever
    thread calls them, which is exactly what `asyncio.to_thread` is
    for. This reuses the same real, official, tested checkpoint
    schema/protocol `langgraph-checkpoint-postgres` already implements
    — no reimplementation of checkpoint serialization/versioning from
    scratch, just a different transport underneath it.
    """

    def __init__(self, sync_saver: PostgresSaver) -> None:
        super().__init__(serde=sync_saver.serde)
        self._sync = sync_saver

    @property
    def conn(self) -> Connection:
        """Exposed for lifespan.py's shutdown cleanup (`await conn.close()`-style)."""
        return self._sync.conn

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        return await asyncio.to_thread(self._sync.get_tuple, config)

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        # Materialized eagerly in the worker thread rather than iterated
        # lazily across thread boundaries — simpler, and checkpoint lists
        # in this app are bounded by one conversation's turn count, not
        # an unbounded stream worth streaming incrementally.
        items = await asyncio.to_thread(
            lambda: list(
                self._sync.list(config, filter=filter, before=before, limit=limit)
            )
        )
        for item in items:
            yield item

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return await asyncio.to_thread(
            self._sync.put, config, checkpoint, metadata, new_versions
        )

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        await asyncio.to_thread(
            self._sync.put_writes, config, writes, task_id, task_path
        )

    async def adelete_thread(self, thread_id: str) -> None:
        await asyncio.to_thread(self._sync.delete_thread, thread_id)


async def create_postgres_checkpointer() -> ThreadedPostgresSaver:
    """
    Opens a dedicated psycopg connection — separate from the app's own
    asyncpg/SQLAlchemy engine, since LangGraph's official Postgres
    checkpoint package doesn't integrate through an arbitrary ORM/engine —
    and runs the one-time `.setup()` schema creation (mirrors this
    project's existing idempotent-schema-setup idiom, see
    packages/api/lifespan.py's `Base.metadata.create_all()`).

    Uses a plain *synchronous* psycopg connection wrapped in
    `ThreadedPostgresSaver` (above), not `AsyncPostgresSaver` — see that
    class's docstring for why. Both the connection and `.setup()` are
    genuinely blocking calls, so both run via `asyncio.to_thread()` too,
    rather than blocking the event loop during startup.

    Called once at app startup (packages/api/lifespan.py), which then
    overrides the `checkpointer` provider below with the real instance
    this returns. Deliberately NOT wired as the provider's own factory:
    dependency_injector's async `providers.Resource` always returns an
    awaitable on every call, even after initialization, which the
    surrounding synchronous provider graph (GraphBuilder, itself
    Factory-wired) has no way to await transparently — confirmed live
    before committing to this design, not assumed.
    """

    conn = await asyncio.to_thread(
        Connection.connect,
        _to_psycopg_dsn(app_settings.database.url),
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
    )

    sync_saver = PostgresSaver(conn=conn, serde=_CHECKPOINT_SERDE)

    await asyncio.to_thread(sync_saver.setup)

    return ThreadedPostgresSaver(sync_saver)


class GraphContainer(containers.DeclarativeContainer):

    settings = providers.DependenciesContainer()
    ai = providers.DependenciesContainer()
    rag = providers.DependenciesContainer()
    tools = providers.DependenciesContainer()
    memory = providers.DependenciesContainer()
    services = providers.DependenciesContainer()
    prompt_builder = providers.Singleton(PromptBuilder)

    # NOTE: this whole chain is Factory, not Singleton, on purpose.
    # extract_memory/load_memory ultimately depend on a DB session
    # (via memory.manager -> repositories.memory), and that session is
    # only valid for the lifetime of one request (see
    # packages/api/dependencies.py's request_scoped_session). A Singleton
    # here would be constructed once — the first time anything touches
    # it, e.g. lifespan.py's startup graph.png render, long before any
    # request-scoped session exists — and then every later request would
    # silently reuse that one stale, never-committed session forever.

    query_analyzer = providers.Factory(
        QueryAnalyzer,
        llm=ai.manager,
    )

    planner = providers.Factory(
        GraphPlanner,
        query_analyzer=query_analyzer,
    )

    load_memory = providers.Factory(
        LoadMemoryNode,
        memory_manager=memory.manager,
    )

    retrieve = providers.Factory(
        RetrieveNode,
        knowledge_manager=rag.knowledge_manager,
        reranker=rag.reranker,
    )

    tool = providers.Factory(
        GraphToolNode,
        tool_manager=tools.manager,
    )

    llm = providers.Factory(
        LLMNode,
        chat_service=services.chat,
        prompt_builder=prompt_builder,
        tool_manager=tools.manager,
    )

    # No longer wired into `nodes`/the compiled graph — it's constructed
    # directly by packages/api/routers/chat.py as a background task
    # after the response is sent, inside a fresh request-scoped session
    # (same reasoning as the comment atop this class: this Factory
    # depends on a per-request DB session that doesn't exist anymore by
    # the time a background task runs, unless it's resolved fresh).
    extract_memory = providers.Factory(
        ExtractMemoryNode,
        memory_manager=memory.manager,
    )

    nodes = providers.Factory(
        GraphNodes,
        planner=planner,
        load_memory=load_memory,
        retrieve=retrieve,
        tool=tool,
        llm=llm,
    )

    router = providers.Factory(
        GraphRouter,
    )

    # In-memory fallback default. Real requests get this overridden at
    # app startup (packages/api/lifespan.py) with a Postgres-backed
    # AsyncPostgresSaver via create_postgres_checkpointer() above, so
    # checkpoints survive a process restart — this MemorySaver only stays
    # live for code paths that construct ApplicationContainer() directly
    # without running through lifespan() (ad-hoc scripts, etc.). Still a
    # Singleton for the same reason as before: building it fresh every
    # request (Factory) would discard state before GraphManager._config()'s
    # thread_id scoping could ever reuse it.
    checkpointer = providers.Singleton(
        MemorySaver,
        serde=_CHECKPOINT_SERDE,
    )

    builder = providers.Factory(
        GraphBuilder,
        nodes=nodes,
        router=router,
        checkpointer=checkpointer,
    )

    manager = providers.Factory(
        GraphManager,
        builder=builder,
    )