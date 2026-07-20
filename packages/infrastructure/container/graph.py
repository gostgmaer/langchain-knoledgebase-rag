# Container graph setup
from __future__ import annotations

from dependency_injector import containers
from dependency_injector import providers

from packages.graph.builder import GraphBuilder
from packages.graph.manager import GraphManager
from packages.graph.nodes import GraphNodes
from packages.graph.router import GraphRouter

from packages.graph.nodes.planner import GraphPlanner
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
    prompt_builder = providers.Dependency()

    planner = providers.Singleton(
        GraphPlanner,
    )

    load_memory = providers.Singleton(
        LoadMemoryNode,
        memory_manager=memory.manager,
    )

    retrieve = providers.Singleton(
        RetrieveNode,
        knowledge_manager=rag.knowledge_manager,
    )

    tool = providers.Singleton(
        GraphToolNode,
        tool_manager=tools.manager,
    )

    llm = providers.Singleton(
        LLMNode,
        chat_service=services.chat,
        prompt_builder=prompt_builder,
        system_prompt="You are a helpful assistant.",
    )
    
    extract_memory = providers.Singleton(
        ExtractMemoryNode,
        memory_manager=memory.manager,
    )

    nodes = providers.Singleton(
        GraphNodes,
        planner=planner,
        load_memory=load_memory,
        retrieve=retrieve,
        tool=tool,
        llm=llm,
        extract_memory=extract_memory,
    )

    router = providers.Singleton(
        GraphRouter,
    )

    builder = providers.Singleton(
        GraphBuilder,
        nodes=nodes,
        router=router,
    )

    manager = providers.Singleton(
        GraphManager,
        builder=builder,
    )