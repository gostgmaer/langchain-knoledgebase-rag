# Ordering
from dataclasses import dataclass


@dataclass(slots=True)
class Ordering:
    field: str
    descending: bool = False