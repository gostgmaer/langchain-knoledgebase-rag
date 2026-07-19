# Filters
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class Filter:
    field: str
    value: Any


@dataclass(slots=True)
class SearchFilter(Filter):
    operator: str = "="