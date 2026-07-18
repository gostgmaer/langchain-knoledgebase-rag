from enum import StrEnum


class SearchType(StrEnum):
    SIMILARITY = "SIMILARITY"
    MMR = "MMR"
    HYBRID = "HYBRID"