# Container graph setup
from __future__ import annotations

from dependency_injector import containers
from dependency_injector import providers

from packages.graph.builder import GraphBuilder
from packages.graph.manager import GraphManager
from packages.graph.nodes import GraphNodes
from packages.graph.router import GraphRouter


class GraphContainer(containers.DeclarativeContainer):

    ai = providers.DependenciesContainer()

    rag = providers.DependenciesContainer()

    tools = providers.DependenciesContainer()

    memory = providers.DependenciesContainer()

    nodes = providers.Singleton(
        GraphNodes,
        ai=ai.manager,
        rag=rag.manager,
        tools=tools.manager,
        memory=memory.manager,
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
        memory=memory.manager,
    )