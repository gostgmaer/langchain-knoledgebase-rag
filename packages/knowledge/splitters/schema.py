"""
Splitter schemas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(slots=True)
class SplitRequest:
    """
    Request for splitting a document.
    """

    tenant_id: UUID

    content: str

    metadata: dict[str, object] = field(default_factory=dict)