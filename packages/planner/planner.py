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

logger = get_logger(__name__)


class GraphPlanner:
    """
    Builds this turn's execution plan. Retrieval runs on every turn,
    by design — the model must ground every answer in the knowledge
    base rather than ever falling back to its own training knowledge
    (docs/BUGS.md item 57). When a QueryAnalyzer is available, it still
    rewrites the query to resolve pronouns/context from conversation
    history and generates expansion variants to widen recall; a
    classifier hiccup here only costs query-rewriting quality — it
    never skips retrieval itself, since RetrieveNode already falls
    back to the raw message when no rewritten_query is set.
    """

    def __init__(
        self,
        query_analyzer: QueryAnalyzer | None = None,
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
        # Retrieval — always runs. Query rewriting/expansion is
        # LLM-backed when a QueryAnalyzer is available; on any failure
        # it's simply skipped, not treated as a reason to skip
        # retrieval itself.
        #

        result: dict = {}

        if self._analyzer is not None:
            try:
                analysis = await self._analyzer.analyze(state["messages"])
                result["rewritten_query"] = analysis.rewritten_query
                result["expanded_queries"] = analysis.expanded_queries
            except Exception as exc:
                logger.warning(
                    "Query analysis failed, retrieval will use the raw message",
                    error=str(exc),
                )

        plan.steps.append(
            ExecutionStep(
                capability=Capability.RETRIEVAL,
                reason="Every turn is grounded in the knowledge base, by design.",
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