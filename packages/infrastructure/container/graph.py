# Container graph setup
from __future__ import annotations

from dependency_injector import containers
from dependency_injector import providers

from packages.graph.builder import GraphBuilder
from packages.graph.manager import GraphManager
from packages.graph.nodes import GraphNodes, NodeContext
from packages.graph.router import GraphRouter
from packages.graph.nodes.planner import GraphPlanner


class GraphContainer(containers.DeclarativeContainer):

    ai = providers.DependenciesContainer()

    rag = providers.DependenciesContainer()

    tools = providers.DependenciesContainer()

    memory = providers.DependenciesContainer()

    runtime = providers.Dependency()

    planner = providers.Singleton(
        GraphPlanner,
    )

    context = providers.Factory(
        NodeContext,
        runtime=runtime,
        rag=rag.manager,
        tools=tools.manager,
        memory=memory.manager,
        planner=planner,
    )

    nodes = providers.Singleton(
        GraphNodes,
        context=context,
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