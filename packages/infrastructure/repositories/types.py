# Types
from __future__ import annotations

from typing import Any, TypeVar

from packages.domain.models.base import BaseModel

ModelType = TypeVar("ModelType", bound=BaseModel)

FilterValue = str | int | float | bool | None

FilterDict = dict[str, FilterValue]

OrderField = tuple[str, bool]

PrimaryKey = Any