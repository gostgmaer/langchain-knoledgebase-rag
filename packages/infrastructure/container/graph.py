# Container graph setup
from __future__ import annotations

from dependency_injector import containers
from dependency_injector import providers

from packages.graph.builder import GraphBuilder
from packages.graph.manager import GraphManager
from packages.graph.nodes import GraphNodes
from packages.graph.router import GraphRouter
from packages.prompts.builder import PromptBuilder

from packages.planner.planner import GraphPlanner
from packages.graph.nodes.load_memory import LoadMemoryNode
from packages.graph.nodes.retrieve import RetrieveNode
from packages.graph.nodes.tool import GraphToolNode
from packages.graph.nodes.llm import LLMNode
from packages.graph.nodes.extract_memory import ExtractMemoryNode


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

    planner = providers.Factory(
        GraphPlanner,
    )

    load_memory = providers.Factory(
        LoadMemoryNode,
        memory_manager=memory.manager,
    )

    retrieve = providers.Factory(
        RetrieveNode,
        knowledge_manager=rag.knowledge_manager,
    )

    tool = providers.Factory(
        GraphToolNode,
        tool_manager=tools.manager,
    )

    llm = providers.Factory(
        LLMNode,
        chat_service=services.chat,
        prompt_builder=prompt_builder,
        system_prompt="You are a helpful assistant.",
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

    builder = providers.Factory(
        GraphBuilder,
        nodes=nodes,
        router=router,
    )

    manager = providers.Factory(
        GraphManager,
        builder=builder,
    )