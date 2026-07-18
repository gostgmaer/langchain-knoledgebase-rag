from dataclasses import dataclass


@dataclass(slots=True)
class SearchResult:
    content: str
    score: float
    metadata: dict