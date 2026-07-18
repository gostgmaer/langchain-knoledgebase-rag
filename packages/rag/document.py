# RAG document
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class RAGDocument:
    """Document flowing through the RAG pipeline."""

    id: str | None = None
    source: str | None = None
    content: str = ""
    metadata: dict[str, object] = field(default_factory=dict)