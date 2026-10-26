"""Tests for app.ingestion.loaders: every format, every failure type, and text cleanup."""

import hashlib
from pathlib import Path

import pytest

from app.config import Settings
from app.ingestion.loaders import (
    PAGE_BREAK,
    DocumentParseError,
    EmptyDocumentError,
    FileTooLargeError,
    ScannedDocumentError,
    UnsupportedFileTypeError,
    load_document,
    normalize_text,
)
from scripts.make_sample_docs import build_pdf

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "sample_docs"


@pytest.mark.parametrize(
    ("file_name", "file_type", "expected_phrase"),
    [
        ("orbit_handbook.md", ".md", "## Connecting to Wi-Fi"),
        ("orbit_faq.txt", ".txt", "Does the Orbit T2 work with a heat pump?"),
        ("orbit_troubleshooting.pdf", ".pdf", "E-207 Wi-Fi connection failed"),
        ("lumen_warranty_returns.docx", ".docx", "two-year limited warranty"),
    ],
)
def test_each_sample_format_loads(
    settings: Settings, file_name: str, file_type: str, expected_phrase: str
) -> None:
    path = SAMPLES / file_name
    document = load_document(path, settings)
    assert document.source == file_name
    assert document.file_type == file_type
    assert expected_phrase in document.text
    assert document.content_hash == hashlib.sha256(path.read_bytes()).hexdigest()
    assert document.size_bytes == path.stat().st_size
    assert document.warnings == ()


def test_docx_headings_become_markdown_headings(settings: Settings) -> None:
    document = load_document(SAMPLES / "lumen_warranty_returns.docx", settings)
    assert "# Limited warranty" in document.text
    assert "## How to make a warranty claim" in document.text


def test_pdf_keeps_page_breaks_and_counts_pages(settings: Settings) -> None:
    document = load_document(SAMPLES / "orbit_troubleshooting.pdf", settings)
    assert document.page_count == 2
    assert document.text.count(PAGE_BREAK) == 1
    assert "Common problems" in document.text.split(PAGE_BREAK)[1]


def test_unsupported_type_is_rejected(settings: Settings, tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("a,b\n1,2\n")
    with pytest.raises(UnsupportedFileTypeError, match="'.csv' is not supported"):
        load_document(path, settings)


@pytest.mark.parametrize("content", ["", "   \n\n\t  \n"])
def test_empty_text_file_is_rejected(settings: Settings, tmp_path: Path, content: str) -> None:
    path = tmp_path / "empty.txt"
    path.write_text(content)
    with pytest.raises(EmptyDocumentError):
        load_document(path, settings)


def test_pdf_without_text_is_detected_as_scanned(settings: Settings, tmp_path: Path) -> None:
    path = tmp_path / "scan.pdf"
    path.write_bytes(build_pdf([[""], [""]]))  # two pages, no text: like scanned images
    with pytest.raises(ScannedDocumentError, match="looks scanned"):
        load_document(path, settings)


def test_partly_scanned_pdf_loads_with_a_warning(settings: Settings, tmp_path: Path) -> None:
    path = tmp_path / "mixed.pdf"
    path.write_bytes(build_pdf([["A page with plenty of real, extractable text on it."], [""]]))
    document = load_document(path, settings)
    assert document.page_count == 2
    assert document.warnings == ("page 2 has almost no text (scanned image or blank page?)",)


@pytest.mark.parametrize(
    ("file_name", "content"),
    [
        ("fake.pdf", b"plain text pretending to be a PDF"),
        ("fake.docx", b"plain text pretending to be a DOCX"),
        ("broken.pdf", b"%PDF-1.4\nthe rest is garbage"),
        ("broken.docx", b"PK\x03\x04the rest is garbage"),
    ],
)
def test_fake_or_damaged_files_are_rejected(
    settings: Settings, tmp_path: Path, file_name: str, content: bytes
) -> None:
    path = tmp_path / file_name
    path.write_bytes(content)
    with pytest.raises(DocumentParseError):
        load_document(path, settings)


def test_oversized_file_is_rejected_before_reading(settings: Settings, tmp_path: Path) -> None:
    path = tmp_path / "big.txt"
    path.write_bytes(b"x" * (1024 * 1024 + 1))
    with pytest.raises(FileTooLargeError, match="1 MB limit"):
        load_document(path, settings.model_copy(update={"max_upload_mb": 1}))


def test_missing_file_raises_file_not_found(settings: Settings, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_document(tmp_path / "nope.md", settings)


def test_non_utf8_text_is_decoded_with_a_warning(settings: Settings, tmp_path: Path) -> None:
    path = tmp_path / "legacy.txt"
    path.write_bytes("Café prices: 5€".encode("cp1252"))
    document = load_document(path, settings)
    assert document.text == "Café prices: 5€"
    assert "Windows-1252" in document.warnings[0]


def test_utf8_bom_is_removed(settings: Settings, tmp_path: Path) -> None:
    path = tmp_path / "bom.md"
    path.write_bytes(b"\xef\xbb\xbf# Title\nBody")
    assert load_document(path, settings).text == "# Title\nBody"


def test_normalize_text_cleans_without_changing_meaning() -> None:
    raw = "Line one   \r\nLine\x00 two\r\n\r\n\r\n\r\nLine three\t\n"
    assert normalize_text(raw) == "Line one\nLine two\n\nLine three"


def test_normalize_text_keeps_page_breaks() -> None:
    assert normalize_text("page one\n\n\f\n\npage two") == "page one\fpage two"
