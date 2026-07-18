from __future__ import annotations

from packages.graph.builder import GraphBuilder
from packages.graph.state import GraphState
from packages.graph.visualizer import GraphVisualizer


class GraphManager:

    def __init__(
        self,
        builder: GraphBuilder,
              
    ) -> None:
        self.graph = builder.build()
        # GraphVisualizer.save_png(self.graph) 

    async def invoke(
        self,
        state: GraphState,
    ):

        return await self.graph.ainvoke(
            state,
        )

    async def stream(
        self,
        state: GraphState,
    ):

        async for event in self.graph.astream(
            state,
        ):
            yield event