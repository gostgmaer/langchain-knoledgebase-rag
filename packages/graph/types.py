# Graph types
from __future__ import annotations

from typing import Annotated, TypeAlias

from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

Messages: TypeAlias = Annotated[
    list[BaseMessage],
    add_messages,
]