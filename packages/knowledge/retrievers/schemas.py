from __future__ import annotations

from dataclasses import dataclass

from packages.domain.models.embedding import Embedding
from packages.knowledge.vectorstores.schema import (
    SearchFilter,
    SearchOptions,
)


@dataclass(slots=True)
class RetrievalRequest:
    """
    Retrieval request.
    """

    query_embedding: Embedding

    filters: SearchFilter

    options: SearchOptions | None = None