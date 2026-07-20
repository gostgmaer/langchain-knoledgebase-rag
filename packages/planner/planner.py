from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from packages.graph.state import GraphState

from .models import (
    Capability,
    ExecutionPlan,
    ExecutionStep,
)
from .rules import RETRIEVAL_KEYWORDS


class GraphPlanner:
    """
    Rule-based planner.

    Later this can be replaced by an LLM planner
    without changing the graph.
    """

    async def __call__(
        self,
        state: GraphState,
    ) -> dict:

        message = state["messages"][-1].content.lower()

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
        # Retrieval
        #

        if any(
            keyword in message
            for keyword in RETRIEVAL_KEYWORDS
        ):
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

        return {"execution_plan": plan}