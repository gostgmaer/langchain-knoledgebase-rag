"""
packages/graph/nodes/supervisor.py
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from packages.graph.state import GraphState
from packages.infrastructure.ai.manager import LLMManager
from packages.shared.logging import get_logger

logger = get_logger(__name__)


class SubQuestionPlan(BaseModel):
    is_multi_part: bool = Field(
        description=(
            "Whether this question genuinely requires independent "
            "sub-investigations (e.g. comparing/synthesizing across "
            "multiple sources or angles) rather than one direct lookup."
        )
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


class SupervisorNode:
    """
    Decides whether the current turn's question is genuinely multi-part
    (needs independent sub-investigations, Multi-Agent's driving gap:
    "multi-part comparison/synthesis questions come out shallow",
    docs/mvpRAG.md v2.0) or should go through the existing single-
    question retrieve->llm path unchanged.

    Hard fail-open guarantee: any LLM error, or a response that claims
    is_multi_part=True with zero real sub-questions, is treated as
    is_multi_part=False — this must never crash and must never route
    into Researcher with nothing to research, since it protects the
    entire existing, heavily-tested single-question path.
    """

    def __init__(self, llm: LLMManager) -> None:
        self._chain = llm.with_structured_output(SubQuestionPlan)

    async def __call__(
        self,
        state: GraphState,
    ) -> GraphState:

        query = state.get("rewritten_query") or state["messages"][-1].content

        try:
            plan = await self._chain.ainvoke(
                "Decide whether the following question genuinely "
                "requires decomposing into independent sub-"
                "investigations to answer well (e.g. it asks to "
                "compare, contrast, or synthesize across multiple "
                "sources or angles), versus a single direct lookup. "
                "If it does, break it into 2-5 independent, self-"
                "contained sub-questions.\n\n"
                f"Question: {query}"
            )
        except Exception as exc:
            logger.warning(
                "Supervisor decomposition failed, falling through to single-question path",
                error=str(exc),
            )
            plan = SubQuestionPlan(is_multi_part=False, sub_questions=[])

        is_multi_part = plan.is_multi_part and bool(plan.sub_questions)

        state["is_multi_part"] = is_multi_part
        state["sub_questions"] = plan.sub_questions if is_multi_part else []

        return state
