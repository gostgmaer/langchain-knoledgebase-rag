"""
Knowledge chunk schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.documents import Document


@dataclass(slots=True)
class KnowledgeChunk:
    """
    Represents a chunk produced after splitting.
    """

    id: str

    document: Document

    embedding: list[float] | None = None

    score: float | None = None

    metadata: dict[str, object] = field(default_factory=dict)