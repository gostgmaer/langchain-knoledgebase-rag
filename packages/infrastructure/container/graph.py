# Container graph setup
from __future__ import annotations

from dependency_injector import containers
from dependency_injector import providers
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

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
        extract_memory=extract_memory,
    )

    router = providers.Factory(
        GraphRouter,
    )

    # Unlike the nodes above, the checkpointer holds no per-request DB
    # session — it's just an in-memory dict of graph state keyed by
    # thread_id. Building it fresh every request (as a Factory) would
    # silently discard it before it could ever be reused, since
    # GraphManager._config() already scopes every call by thread_id
    # (== conversation_id). Singleton here lets checkpoints genuinely
    # persist across requests for the lifetime of the process.
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