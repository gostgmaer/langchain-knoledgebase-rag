# Query analyzer — LLM-backed classification, rewriting, expansion
from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from packages.shared.logging import get_logger

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage

    from packages.infrastructure.ai.manager import LLMManager

logger = get_logger(__name__)


class QueryAnalysis(BaseModel):
    """
    One structured-output LLM call doing three roadmap items at once:
    deciding whether retrieval is needed at all, rewriting the raw
    query to resolve pronouns/context from conversation history, and
    generating a few related variants to widen recall.
    """

    needs_retrieval: bool = Field(
        description="Whether answering this message requires looking up stored documents.",
    )

    rewritten_query: str = Field(
        description=(
            "The user's question rewritten as a standalone search query, "
            "resolving pronouns and implicit context from the conversation "
            "history (e.g. 'what's its battery life?' -> 'What is the "
            "battery life of Unit-9?'). If already standalone, return it "
            "unchanged."
        ),
    )

    expanded_queries: list[str] = Field(
        default_factory=list,
        max_length=3,
        description=(
            "0-3 alternative phrasings or related queries that would "
            "widen search recall for the same underlying question. "
            "Empty if the query is already specific enough."
        ),
    )


class QueryAnalyzer:
    """
    Wraps a single LLMManager.with_structured_output(QueryAnalysis)
    call. Callers must fail open to a rule-based fallback on any
    error here (see GraphPlanner) — a classifier hiccup should never
    crash a turn.
    """

    def __init__(
        self,
        llm: LLMManager,
    ) -> None:
        self._chain = llm.with_structured_output(QueryAnalysis)

    async def analyze(
        self,
        messages: list[BaseMessage],
    ) -> QueryAnalysis:

        history = "\n".join(
            f"{message.type}: {message.content}"
            for message in messages[-6:]
        )

        return await self._chain.ainvoke(
            "Conversation so far:\n\n"
            f"{history}\n\n"
            "Analyze the most recent user message above."
        )
