import pytest

from packages.knowledge.exceptions import UnsupportedDocumentError
from packages.knowledge.loaders.factory import LoaderFactory


def test_supported_extensions_matches_what_create_actually_accepts():
    """
    Guards against the two ever drifting apart — the upload route
    (packages/api/routers/documents.py) rejects a file before ever
    reading it based on this set, so it must exactly match what
    create() would otherwise raise UnsupportedDocumentError for.
    """
    for extension in LoaderFactory.supported_extensions():
        loader = LoaderFactory.create(f"document{extension}")
        assert loader is not None


def test_unsupported_extension_is_not_in_the_supported_set():
    assert ".exe" not in LoaderFactory.supported_extensions()
    with pytest.raises(UnsupportedDocumentError):
        LoaderFactory.create("malicious.exe")


def test_supported_extensions_includes_the_common_document_types():
    extensions = LoaderFactory.supported_extensions()

    for expected in (".pdf", ".docx", ".txt", ".md", ".html", ".csv", ".json"):
        assert expected in extensions
