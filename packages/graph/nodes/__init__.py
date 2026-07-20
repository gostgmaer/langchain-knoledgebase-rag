# init
from dataclasses import dataclass

from langgraph.prebuilt import ToolNode

from packages.graph.nodes.extract_memory import ExtractMemoryNode
from packages.graph.nodes.llm import LLMNode
from packages.graph.nodes.load_memory import LoadMemoryNode
from packages.planner.planner import GraphPlanner
from packages.graph.nodes.retrieve import RetrieveNode

# from .planner import GraphPlanner
# from .load_memory import LoadMemoryNode
# from .retrieve import RetrieveNode
# from .tool import ToolNode
# from .llm import LLMNode
# from .extract_memory import ExtractMemoryNode


@dataclass(slots=True)
class GraphNodes:

    planner: GraphPlanner

    load_memory: LoadMemoryNode

    retrieve: RetrieveNode

    tool: ToolNode

    llm: LLMNode

    extract_memory: ExtractMemoryNode
