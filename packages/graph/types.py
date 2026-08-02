# Graph types
from __future__ import annotations

from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

type Messages = Annotated[
    list[BaseMessage],
    add_messages,
]