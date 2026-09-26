from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from packages.api.routers.documents import _chunking_info, _document_responses
from packages.knowledge.splitters.factory import SplitterFactory


# ---- which strategy actually runs ---------------------------------------------------
@pytest.mark.parametrize(
    ("requested", "extension", "effective"),
    [
        ("auto", ".md", "markdown"),
        ("auto", ".markdown", "markdown"),
        ("auto", ".txt", "recursive"),
        ("auto", ".pdf", "recursive"),
        ("auto", "", "recursive"),
        ("recursive", ".md", "recursive"),  # an explicit choice is never overridden
        ("markdown", ".txt", "markdown"),
        ("semantic", ".txt", "semantic"),
    ],
)
def test_resolve_reports_the_strategy_that_will_run(requested, extension, effective):
    assert SplitterFactory.resolve(strategy=requested, file_extension=extension) == effective


def test_create_and_resolve_agree():
    recursive, markdown, semantic = object(), object(), object()
    factory = SplitterFactory(recursive, markdown, semantic)

    assert factory.create(strategy="auto", file_extension=".md") is markdown
    assert factory.create(strategy="auto", file_extension=".txt") is recursive
    assert factory.create(strategy="semantic", file_extension=".md") is semantic
    assert factory.create(strategy="recursive", file_extension=".md") is recursive


# ---- the document-level record ---------------------------------------------------------
def test_chunking_info_is_read_from_the_document_metadata():
    info = _chunking_info(
        {
            "chunking": {
                "requested": "auto",
                "strategy": "markdown",
                "splitter": "MarkdownDocumentSplitter",
                "chunk_size": 1000,
                "chunk_overlap": 200,
                "chunk_count": 7,
                "total_tokens": 812,
            },
            "other": "kept elsewhere",
        }
    )

    assert info.requested == "auto"
    assert info.strategy == "markdown"
    assert info.chunk_count == 7


@pytest.mark.parametrize("metadata", [None, {}, {"chunking": None}, {"chunking": "junk"}])
def test_documents_ingested_before_chunking_was_recorded_have_no_record(metadata):
    assert _chunking_info(metadata) is None


# ---- API objects ------------------------------------------------------------------------
class _FakeChunkRepo:
    def __init__(self, counts):
        self._counts = counts

    async def count_primary_by_documents(self, ids):
        return {i: self._counts[i] for i in ids if i in self._counts}


def _container(counts):
    return SimpleNamespace(repositories=SimpleNamespace(document_chunk=lambda: _FakeChunkRepo(counts)))


def _doc(**over):
    now = datetime.now(UTC)
    base = dict(
        id=uuid4(),
        knowledge_base_id=uuid4(),
        title="Guide",
        description=None,
        file_id="f1",
        file_name="guide.md",
        mime_type="text/markdown",
        extension=".md",
        size_bytes=10,
        status=SimpleNamespace(value="READY"),
        is_current=True,
        created_at=now,
        updated_at=now,
        metadata_={"chunking": {"requested": "auto", "strategy": "markdown"}, "source": "upload"},
        checksum="abc",
        uploaded_by=None,
        source_type=None,
        processing_version=None,
        parser_name=None,
        chunking_version=None,
        embedding_provider=None,
        embedding_model=None,
        embedding_dimensions=None,
        processing_stage=None,
        error_reason=None,
        processed_at=None,
        visibility=None,
        document_type=None,
        category=None,
        tags=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_documents_carry_chunk_counts_chunking_and_metadata():
    with_chunks = _doc()
    empty = _doc(file_name="empty.txt", metadata_=None)

    out = await _document_responses(_container({with_chunks.id: (5, 2)}), [with_chunks, empty])

    assert out[0].chunk_count == 5
    assert out[0].representation_count == 2
    assert out[0].chunking.strategy == "markdown"
    assert out[0].document_metadata["source"] == "upload"
    assert out[0].status == "READY"
    # no rows in the count query -> zero chunks, no record, empty metadata
    assert out[1].chunk_count == 0
    assert out[1].chunking is None
    assert out[1].document_metadata == {}


# ---- no server paths in chunk metadata --------------------------------------------------
def test_scratch_paths_are_replaced_with_the_document_name():
    from packages.api.routers.documents import _public_chunk_metadata

    cleaned = _public_chunk_metadata(
        {
            "source": "storage/temp/50eb2f87_guide.md",
            "filename": "50eb2f87-6e00-4bb7-b472-7d20ad5fec1e_guide.md",
            "h1": "Title",
        },
        "guide.md",
    )

    assert cleaned["source"] == "guide.md"
    assert cleaned["filename"] == "guide.md"
    assert cleaned["h1"] == "Title"


def test_clean_metadata_is_left_alone_and_none_is_safe():
    from packages.api.routers.documents import _public_chunk_metadata

    assert _public_chunk_metadata({"source": "guide.md", "page": 2}, "guide.md") == {"source": "guide.md", "page": 2}
    assert _public_chunk_metadata(None, "guide.md") == {}
