# init
from dataclasses import dataclass

from langgraph.prebuilt import ToolNode

from packages.graph.nodes.llm import LLMNode
from packages.graph.nodes.load_memory import LoadMemoryNode
from packages.planner.planner import GraphPlanner
from packages.graph.nodes.retrieve import RetrieveNode

# extract_memory (packages/graph/nodes/extract_memory.py) is no longer
# a graph node — packages/graph/builder.py's docstring and
# packages/api/routers/chat.py explain why. Still constructed via DI
# (packages/infrastructure/container/graph.py's own `extract_memory`
# provider), just called directly as a background task, not through
# GraphNodes/the compiled graph.


@dataclass(slots=True)
class GraphNodes:

    planner: GraphPlanner

    load_memory: LoadMemoryNode

    retrieve: RetrieveNode

    tool: ToolNode

    llm: LLMNode
