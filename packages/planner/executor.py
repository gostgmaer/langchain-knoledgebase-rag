from __future__ import annotations

from packages.graph.state import GraphState

from .models import (
    Capability,
    ExecutionPlan,
)


class ExecutionEngine:
    """
    Executes an execution plan.

    Initially this engine only decides the next capability.

    Later it will support:
    - multi-step execution
    - parallel execution
    - retries
    - replanning
    """

    def next_capability(
        self,
        plan: ExecutionPlan,
    ) -> Capability:

        if not plan.steps:
            return Capability.LLM

        return plan.first_step.capability

    def should_execute(
        self,
        plan: ExecutionPlan,
        capability: Capability,
    ) -> bool:

        return plan.has(capability)