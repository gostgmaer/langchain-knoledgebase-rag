"""
packages/memory/schemas.py

AI Memory Domain Models

This module defines the contracts used by the AI Memory subsystem.
These models are independent of LangGraph, vector databases,
and persistence implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class MemoryType(StrEnum):
    """Supported memory categories."""

    FACT = "fact"
    PREFERENCE = "preference"
    PROFILE = "profile"
    TASK = "task"
    SUMMARY = "summary"
    GOAL = "goal"
    SKILL = "skill"
    PROJECT = "project"


@dataclass(slots=True)
class MemoryFact:
    """
    A single piece of long-term AI memory.
    """

    id: UUID = field(default_factory=uuid4)

    tenant_id: UUID | None = None

    user_id: UUID | None = None

    conversation_id: UUID | None = None

    type: MemoryType = MemoryType.FACT

    content: str = ""

    importance: float = 0.5

    metadata: dict[str, Any] = field(default_factory=dict)

    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    updated_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )


@dataclass(slots=True)
class CreateMemoryRequest:
    """
    Request to create a new memory.
    """

    type: MemoryType

    content: str

    tenant_id: UUID | None = None

    user_id: UUID | None = None

    conversation_id: UUID | None = None

    importance: float = 0.5

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class UpdateMemoryRequest:
    """
    Request to update an existing memory.
    """

    content: str | None = None

    importance: float | None = None

    metadata: dict[str, Any] | None = None


@dataclass(slots=True)
class SearchMemoryRequest:
    """
    Semantic memory search request.
    """

    query: str

    tenant_id: UUID | None = None

    user_id: UUID | None = None

    top_k: int = 5

    minimum_score: float = 0.70


@dataclass(slots=True)
class SearchResult:
    """
    Single memory search result.
    """

    memory: MemoryFact

    score: float


@dataclass(slots=True)
class SearchMemoryResponse:
    """
    Semantic memory search response.
    """

    results: list[SearchResult] = field(default_factory=list)

    total: int = 0