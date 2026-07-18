# Tool models
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ToolMetadata:

    name: str

    description: str

    version: str = "1.0"

    tags: list[str] | None = None


@dataclass(slots=True)
class ToolExecutionResult:

    success: bool

    output: Any

    metadata: dict[str, Any] | None = None