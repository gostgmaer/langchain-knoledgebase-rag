from enum import StrEnum


class SimilarityMetric(StrEnum):
    COSINE = "COSINE"
    DOT_PRODUCT = "DOT_PRODUCT"
    EUCLIDEAN = "EUCLIDEAN"