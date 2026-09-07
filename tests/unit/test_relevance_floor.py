"""
apply_relevance_floor (packages/knowledge/reranking/cross_encoder.py)
— the fix for a previously-unreproduced bug (docs/BUILD_STATUS.md:
"empty citations on an otherwise-correct RAG answer"), now root-caused
live: this cross-encoder's raw logits don't reliably separate
"irrelevant" from "relevant but vaguely/pronoun-phrased" — a real
follow-up like "is it safe?" scored -8.25 against its genuinely correct
chunk in a live probe, the same band as clearly off-topic pairs. The
original uniform floor (drop every candidate below min_score) could
therefore empty citations/context on a turn that genuinely found the
right answer. Fixed by always keeping the single best-ranked candidate;
the floor still trims weaker stragglers ranked below it.
"""

from uuid import uuid4

from packages.domain.models.document_chunk import DocumentChunk
from packages.knowledge.reranking.cross_encoder import apply_relevance_floor
from packages.knowledge.vectorstores.schema import SearchResult


def _chunk(content: str = "chunk content") -> DocumentChunk:
    return DocumentChunk(
        id=uuid4(),
        tenant_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        content=content,
        token_count=1,
        character_count=len(content),
        metadata_={},
    )


def test_top_result_survives_even_when_below_the_floor():
    """
    The exact reproduced bug: a single, genuinely correct candidate
    scores below the default 0.0 floor (e.g. -0.02, empirically
    measured for a real vague follow-up query against its correct
    chunk) — it must not be silently dropped down to zero citations.
    """

    reranked = [SearchResult(chunk=_chunk(), score=-0.02)]

    result = apply_relevance_floor(reranked, min_score=0.0)

    assert len(result) == 1
    assert result[0].score == -0.02


def test_floor_still_trims_weaker_stragglers_below_top_result():
    reranked = [
        SearchResult(chunk=_chunk("best match"), score=5.0),
        SearchResult(chunk=_chunk("weak straggler"), score=-3.0),
        SearchResult(chunk=_chunk("borderline"), score=1.0),
    ]

    result = apply_relevance_floor(reranked, min_score=0.0)

    assert [r.chunk.content for r in result] == ["best match", "borderline"]


def test_empty_input_stays_empty():
    assert apply_relevance_floor([], min_score=0.0) == []


def test_all_results_above_floor_are_all_kept():
    reranked = [
        SearchResult(chunk=_chunk("a"), score=5.0),
        SearchResult(chunk=_chunk("b"), score=2.0),
    ]

    result = apply_relevance_floor(reranked, min_score=0.0)

    assert len(result) == 2
