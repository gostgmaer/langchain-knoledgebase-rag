# embedding.py
"""
Knowledge embedding schemas.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.documents import Document


@dataclass(slots=True)
class DocumentChunk:
    """
    Represents a document and its embedding.
    """

    document: Document

    embedding: list[float]

    dimensions: int

    provider: str

    model: str

    metadata: dict[str, object] = field(default_factory=dict)