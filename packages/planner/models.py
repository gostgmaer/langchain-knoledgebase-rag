from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Capability(StrEnum):
    """
    Execution capabilities supported by the agent.
    """

    MEMORY = "memory"
    RETRIEVAL = "retrieval"
    TOOL = "tool"
    LLM = "llm"

    SUMMARIZATION = "summarization"

    HUMAN = "human"


@dataclass(slots=True, frozen=True)
class ExecutionStep:
    """
    A single execution step.
    """

    capability: Capability

    reason: str


@dataclass(slots=True)
class ExecutionPlan:
    """
    Ordered execution plan.
    """

    steps: list[ExecutionStep] = field(default_factory=list)

    @property
    def first_step(self) -> ExecutionStep:
        return self.steps[0]

    def has(
        self,
        capability: Capability,
    ) -> bool:

        return any(
            step.capability == capability
            for step in self.steps
        )