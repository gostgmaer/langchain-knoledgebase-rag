# semantic.py
"""
Semantic (embedding-similarity) document splitter.
"""

from __future__ import annotations

import math
import re
import statistics

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from packages.config.loader import settings
from packages.knowledge.embeddings.manager import EmbeddingManager

from .base import BaseSplitter

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    return [
        sentence
        for sentence in _SENTENCE_BOUNDARY.split(text.strip())
        if sentence
    ]


def _cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return 1.0 - (dot / (norm_a * norm_b))


class SemanticDocumentSplitter(BaseSplitter):
    """
    Splits text at points of genuine topic change rather than a fixed
    size, by embedding every sentence and breaking wherever the
    distance to the next sentence spikes above the configured
    breakpoint percentile. Hand-rolled (no langchain_experimental
    dependency) to avoid pulling in a package with a history of
    breaking changes for what's a fairly small algorithm.

    Oversized resulting chunks are capped by a recursive character
    split, same as the other splitters, since a run of consecutive
    on-topic sentences can still exceed a usable chunk size.
    """

    def __init__(
        self,
        embeddings: EmbeddingManager,
        breakpoint_percentile: float = 0.95,
    ) -> None:

        self._embeddings = embeddings
        self._breakpoint_percentile = breakpoint_percentile

        self._size_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.rag.chunk_size,
            chunk_overlap=settings.rag.chunk_overlap,
            separators=settings.rag.chunk_separators,
        )

    async def split(
        self,
        documents: list[Document],
    ) -> list[Document]:

        result: list[Document] = []

        for document in documents:
            result.extend(await self._split_one(document))

        return result

    async def _split_one(
        self,
        document: Document,
    ) -> list[Document]:

        sentences = _split_sentences(document.page_content)

        if len(sentences) < 2:
            return [document]

        vectors = await self._embeddings.client.aembed_documents(sentences)

        distances = [
            _cosine_distance(vectors[i], vectors[i + 1])
            for i in range(len(vectors) - 1)
        ]

        threshold = statistics.quantiles(
            distances,
            n=100,
        )[int(self._breakpoint_percentile * 100) - 1]

        chunk_texts: list[str] = []
        current = [sentences[0]]

        for index, distance in enumerate(distances):
            if distance > threshold:
                chunk_texts.append(" ".join(current))
                current = []
            current.append(sentences[index + 1])

        chunk_texts.append(" ".join(current))

        semantic_chunks = [
            Document(page_content=text, metadata=document.metadata)
            for text in chunk_texts
        ]

        return self._size_splitter.split_documents(semantic_chunks)
