# init
from dataclasses import dataclass

from .planner import GraphPlanner
from .load_memory import LoadMemoryNode
from .retrieve import RetrieveNode
from .tool import ToolNode
from .llm import LLMNode
from .extract_memory import ExtractMemoryNode


@dataclass(slots=True)
class GraphNodes:

    planner: GraphPlanner

    load_memory: LoadMemoryNode

    retrieve: RetrieveNode

    tool: ToolNode

    llm: LLMNode

    extract_memory: ExtractMemoryNode
