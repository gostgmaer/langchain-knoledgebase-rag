import pytest
from langchain_core.documents import Document

from packages.knowledge.splitters.recursive import RecursiveDocumentSplitter


@pytest.mark.asyncio
async def test_short_document_stays_a_single_chunk():
    splitter = RecursiveDocumentSplitter()
    doc = Document(page_content="A short sentence that fits well under the chunk size.")

    chunks = await splitter.split([doc])

    assert len(chunks) == 1
    assert chunks[0].page_content == doc.page_content


@pytest.mark.asyncio
async def test_long_document_splits_into_multiple_chunks_near_the_configured_size():
    splitter = RecursiveDocumentSplitter()
    # Configured chunk_size is 1000 — well over 3x that forces >= 3 chunks
    # even accounting for the configured 200-char overlap between them.
    long_text = ("This is one sentence about robotics. " * 200).strip()
    doc = Document(page_content=long_text)

    chunks = await splitter.split([doc])

    assert len(chunks) >= 3
    for chunk in chunks:
        # A soft bound, not exact: RecursiveCharacterTextSplitter prefers
        # breaking on separators over hard-cutting mid-sentence, so a
        # chunk can run a little past chunk_size.
        assert len(chunk.page_content) <= 1200


@pytest.mark.asyncio
async def test_document_metadata_is_preserved_across_every_chunk():
    splitter = RecursiveDocumentSplitter()
    long_text = ("This is one sentence about robotics. " * 200).strip()
    doc = Document(page_content=long_text, metadata={"source": "test.txt", "document_id": "abc-123"})

    chunks = await splitter.split([doc])

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.metadata["source"] == "test.txt"
        assert chunk.metadata["document_id"] == "abc-123"


@pytest.mark.asyncio
async def test_empty_document_list_returns_empty_list():
    splitter = RecursiveDocumentSplitter()

    assert await splitter.split([]) == []
