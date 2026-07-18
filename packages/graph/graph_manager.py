from .builder import build_graph


class GraphManager:

    def __init__(self):
        self._graph = build_graph()

    @property
    def graph(self):
        return self._graph

    def invoke(self, state):
        return self._graph.invoke(state)

    async def ainvoke(self, state):
        return await self._graph.ainvoke(state)

    def stream(self, state):
        yield from self._graph.stream(state)

    async def astream(self, state):
        async for event in self._graph.astream(state):
            yield event