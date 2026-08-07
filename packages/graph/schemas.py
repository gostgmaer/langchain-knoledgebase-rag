# packages/graph/schemas.py
from __future__ import annotations

from dataclasses import dataclass, field

from packages.knowledge.schemas import Citation


@dataclass(slots=True, frozen=True)
class ResearchFinding:
    """One decomposed sub-question's research result — ResearcherNode's
    output, consumed by WriterNode. Reachable from GraphState on every
    multi-part turn, so it must be registered in
    packages/infrastructure/container/graph.py's _CHECKPOINT_SERDE
    allowlist."""

    sub_question: str
    finding: str
    citations: list[Citation] = field(default_factory=list)
