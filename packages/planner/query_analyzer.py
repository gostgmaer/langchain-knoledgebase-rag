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
    One structured-output LLM call doing everything GraphPlanner needs
    from the model before routing: rewriting the raw query to resolve
    pronouns/context from conversation history, generating a few
    related variants to widen recall, AND deciding whether the
    question is genuinely multi-part (docs/BUGS.md item 63 — this used
    to be two separate structured-output calls, GraphPlanner's own
    QueryAnalyzer call and the now-deleted SupervisorNode's, run
    concurrently from START and bounded by whichever was slower; one
    combined call pays one LLM round-trip's worth of fixed per-call
    overhead instead of two, since concurrency overlaps two calls
    against each other but never makes either individually faster).
    Retrieval itself always runs (packages/planner/planner.py) — this
    call only improves what gets searched for and how the turn routes,
    never whether a search happens.
    """

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

    is_multi_part: bool = Field(
        description=(
            "Whether this question genuinely requires independent "
            "sub-investigations (e.g. comparing/synthesizing across "
            "multiple sources or angles) rather than one direct lookup."
        ),
    )

    sub_questions: list[str] = Field(
        default_factory=list,
        max_length=5,
        description=(
            "2-5 independent, self-contained sub-questions that "
            "together answer the original question. Empty if "
            "is_multi_part is false."
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
            "Analyze the most recent user message above. Rewrite it as a "
            "standalone search query and suggest expansion variants. Also "
            "decide whether it genuinely requires decomposing into "
            "independent sub-investigations to answer well (e.g. it asks "
            "to compare, contrast, or synthesize across multiple sources "
            "or angles), versus a single direct lookup. If it does, break "
            "it into 2-5 independent, self-contained sub-questions."
        )
