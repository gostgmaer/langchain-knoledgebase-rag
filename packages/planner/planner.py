from __future__ import annotations

from typing import TYPE_CHECKING

from packages.shared.logging import get_logger

if TYPE_CHECKING:
    from packages.graph.state import GraphState
    from packages.planner.query_analyzer import QueryAnalyzer

from .models import (
    Capability,
    ExecutionPlan,
    ExecutionStep,
)
from .rules import RETRIEVAL_KEYWORDS

logger = get_logger(__name__)


class GraphPlanner:
    """
    Decides whether this turn needs retrieval, and (when a
    QueryAnalyzer is available) rewrites/expands the query via a real
    LLM call. Falls back to rule-based keyword matching whenever the
    analyzer is absent or its call fails — a classifier hiccup should
    never crash a turn, so retrieval routing degrades to the original
    substring-match behavior rather than raising.
    """

    def __init__(
        self,
        query_analyzer: "QueryAnalyzer | None" = None,
    ) -> None:
        self._analyzer = query_analyzer

    async def __call__(
        self,
        state: GraphState,
    ) -> dict:

        plan = ExecutionPlan()

        #
        # Memory
        #

        plan.steps.append(
            ExecutionStep(
                capability=Capability.MEMORY,
                reason="Load long-term memory.",
            )
        )

        #
        # Retrieval — LLM-backed classification/rewriting/expansion,
        # falling back to keyword matching on any failure.
        #

        result: dict = {}
        needs_retrieval = False

        if self._analyzer is not None:
            try:
                analysis = await self._analyzer.analyze(state["messages"])
                needs_retrieval = analysis.needs_retrieval
                result["rewritten_query"] = analysis.rewritten_query
                result["expanded_queries"] = analysis.expanded_queries
            except Exception as exc:
                logger.warning(
                    "Query analysis failed, falling back to keyword matching",
                    error=str(exc),
                )

        if self._analyzer is None or "rewritten_query" not in result:
            message = state["messages"][-1].content.lower()
            needs_retrieval = any(
                keyword in message
                for keyword in RETRIEVAL_KEYWORDS
            )

        if needs_retrieval:
            plan.steps.append(
                ExecutionStep(
                    capability=Capability.RETRIEVAL,
                    reason="Knowledge lookup required.",
                )
            )

        #
        # Final response
        #

        plan.steps.append(
            ExecutionStep(
                capability=Capability.LLM,
                reason="Generate final response.",
            )
        )

        result["execution_plan"] = plan

        return result