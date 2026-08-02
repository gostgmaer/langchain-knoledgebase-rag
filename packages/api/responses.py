# API responses
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApiResponse[T](BaseModel):
    """
    Standard successful API response.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
    )

    success: bool = True

    message: str = "Success"

    data: T | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )


class ErrorResponse(BaseModel):
    """
    Standard error response.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
    )
    success: bool = False
    error: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )